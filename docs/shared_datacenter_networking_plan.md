# Shared Datacenter Networking Plan

## Goal

Reduce the host port surface so TryOps can run on a shared datacenter machine without exposing every backing service to other users.

The design must:

- Expose only necessary user/operator entrypoints.
- Keep databases, queues, metrics backends, traces, logs, model workers, and internal sidecars private.
- Avoid hardcoded public worker ports.
- Keep browser login working.
- Keep Grafana useful for operators.
- Preserve local developer ergonomics as a separate mode.

## Current State

`make app-up` currently publishes many ports to the host. That is convenient on a single-user workstation, but not clean for a multi-user datacenter host.

Developer-local host surface currently includes:

- gateway / console
- FastAPI direct
- Keycloak
- controller
- FASHN VTON host process
- Postgres
- Valkey
- MinIO
- MLflow
- Prometheus
- Alertmanager
- Grafana
- Loki
- Tempo
- OTel collector
- OTel bridge
- guardrail sidecar

This is too open for shared infrastructure.

## Target Principle

Use one stable public ingress surface and keep everything else internal.

```text
external users/operators
  -> ingress / reverse proxy
      -> gateway / console
      -> Keycloak
      -> Grafana

internal networks
  -> API
  -> Postgres
  -> Valkey
  -> MinIO
  -> MLflow
  -> Prometheus
  -> Loki
  -> Tempo
  -> Alertmanager
  -> OTel collector
  -> Guardrail
  -> FASHN router / workers
  -> optional vLLM router / workers
```

The app should depend on service DNS and explicit env vars, not public host ports.

## Recommended Exposure Modes

### Mode A: Production-Like Shared Host With Ingress

Preferred mode.

Host surface:

| Public endpoint | Target | Audience |
| --- | --- | --- |
| `https://tryops.example.com` | `gateway:8081` | End users and admins. |
| `https://auth.tryops.example.com` | `keycloak:8080` | Browser auth only. |
| `https://grafana.tryops.example.com` | `grafana:3000` | Operators only. |

Only ingress binds the public interface:

```text
0.0.0.0:443 -> reverse proxy
```

Everything else is internal service-to-service traffic.

### Mode B: Shared Host Without DNS/Ingress

Acceptable interim mode.

Host surface:

| Host port | Service | Reason |
| --- | --- | --- |
| `18081` | gateway / console | Main application entrypoint. |
| `18082` | Keycloak | Browser OIDC redirects need a reachable auth URL. |
| `13000` | Grafana | Operator dashboard access. Restrict with firewall/VPN. |

Everything else should be internal-only.

### Mode C: Developer-Local Full Exposure

Keep current `make app-up` behavior for single-user development only.

Host surface:

```text
many local-friendly ports
```

This mode is useful for debugging but should not be the shared datacenter default.

## Internal-Only Services

These should not publish host ports in shared mode:

| Service | Internal target |
| --- | --- |
| FastAPI | `api:8080` |
| Postgres | `postgres:5432` |
| Valkey | `valkey:6379` |
| MinIO | `minio:9000` and `minio:9001` |
| MLflow | `mlflow:5000` |
| Prometheus | `prometheus:9090` |
| Alertmanager | `alertmanager:9093` |
| Grafana datasource to Prometheus | `prometheus:9090` |
| Loki | `loki:3100` |
| Tempo | `tempo:3200` |
| OTel collector | `otel-collector:4317`, `4318`, `8888`, `13133` |
| OTel bridge | `tryops-otel-bridge:19122` |
| Guardrail | `guardrail:18083` |
| FASHN serving | `fashn-vton-router:18100` or private host bridge |
| vLLM serving | `vllm-router:8000` or external OpenAI endpoint |

Direct access for maintenance should use SSH tunnels, VPN, or admin-only ingress routes, not permanent public host ports.

## Model Serving Abstraction

The app should know one model-serving URL per model family:

```env
TRYOPS_REAL_VTON_URL=http://fashn-vton-router:18100
TRYOPS_LLM_BASE_URL=http://vllm-router:8000/v1
```

If OpenAI is used:

```env
TRYOPS_LLM_BASE_URL=https://api.openai.com/v1
```

For the current host-side FASHN process, use a private bridge only as an interim implementation detail:

```env
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100
```

Shared-mode target:

```text
API
  -> FASHN router
      -> private GPU workers
```

The API, frontend, and Prometheus config should not know worker ports.

## Auth Design

Browser OIDC requires the browser to reach Keycloak.

With ingress:

```env
TRYOPS_KEYCLOAK_PUBLIC_URL=https://auth.tryops.example.com
TRYOPS_GATEWAY_OIDC_ISSUER=https://auth.tryops.example.com/realms/tryops
```

Internal service calls should still use internal DNS:

```env
TRYOPS_GATEWAY_OIDC_JWKS_URL=http://keycloak:8080/realms/tryops/protocol/openid-connect/certs
```

Without ingress:

```env
TRYOPS_KEYCLOAK_PUBLIC_URL=http://host.example.com:18082
TRYOPS_GATEWAY_OIDC_ISSUER=http://host.example.com:18082/realms/tryops
```

Do not expose direct API auth fallback in shared mode.

## Observability Design

Grafana is the operator UI. Prometheus, Loki, Tempo, Alertmanager, and OTel collector should remain internal.

External/operator access:

```text
operator browser -> grafana
```

Internal datasource flow:

```text
grafana -> prometheus:9090
grafana -> loki:3100
grafana -> tempo:3200
prometheus -> api:8080/metrics
prometheus -> gateway:8081/metrics
prometheus -> guardrail:18083/metrics
prometheus -> otel-collector:8888/metrics
prometheus -> dcgm-exporter:9400
prometheus -> node-exporter:9100
prometheus -> process-exporter:9256
```

Do not expose Loki, Tempo, Prometheus, or Alertmanager directly to general users.

## Compose Design

Add a shared override:

```text
docker-compose.shared.yml
```

Purpose:

- Remove or override unnecessary `ports:` mappings.
- Keep only gateway, Keycloak, and Grafana if no ingress is used.
- Or keep only ingress if a reverse proxy is added.
- Add internal exporter services.
- Keep FASHN/vLLM endpoints private.

Example no-ingress shared override:

```yaml
services:
  api:
    ports: []

  postgres:
    ports: []

  valkey:
    ports: []

  minio:
    ports: []

  mlflow:
    ports: []

  prometheus:
    ports: []

  alertmanager:
    ports: []

  loki:
    ports: []

  tempo:
    ports: []

  otel-collector:
    ports: []

  guardrail:
    ports: []

  gateway:
    ports:
      - "${TRYOPS_GATEWAY_PORT:-18081}:8081"

  keycloak:
    ports:
      - "${TRYOPS_KEYCLOAK_PORT:-18082}:8080"

  grafana:
    ports:
      - "${TRYOPS_GRAFANA_PORT:-13000}:3000"
```

Example ingress shared override:

```yaml
services:
  gateway:
    ports: []

  keycloak:
    ports: []

  grafana:
    ports: []

  ingress:
    image: nginx:stable
    ports:
      - "${TRYOPS_HTTPS_PORT:-443}:443"
    depends_on:
      - gateway
      - keycloak
      - grafana
```

Exact Compose syntax needs validation because list replacement semantics can be subtle. Acceptance must include `docker compose config` output inspection.

## Make Targets

Add:

```text
make app-up-shared
make app-down-shared
make app-shared-ports
```

Behavior:

- `app-up`: developer-local full exposure.
- `app-up-shared`: reduced shared-host exposure.
- `app-shared-ports`: prints the actual published host ports from Docker.

Example:

```bash
make app-up-shared
docker compose -f docker-compose.yml -f docker-compose.observability.yml -f docker-compose.shared.yml ps
```

## Firewall Policy

Shared datacenter hosts should also enforce host firewall rules.

Allowed from user/operator network:

- ingress `443`, or
- interim ports `18081`, `18082`, `13000`

Blocked from user/operator network:

- database ports
- queue/cache ports
- Prometheus/Loki/Tempo
- model worker/router ports unless explicitly private to API network
- OTel receiver ports
- MinIO/MLflow unless operator-only

## Validation

### Static Validation

Run:

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml -f docker-compose.shared.yml config --quiet
```

Inspect published ports:

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml -f docker-compose.shared.yml config | grep -A5 'ports:'
```

Expected no-ingress shared mode:

```text
gateway -> host port 18081
keycloak -> host port 18082
grafana -> host port 13000
```

Expected ingress mode:

```text
ingress -> host port 443
```

### Runtime Validation

From host:

```bash
curl -fsS http://127.0.0.1:18081/health
curl -fsS http://127.0.0.1:18082/realms/tryops/.well-known/openid-configuration
curl -fsS http://127.0.0.1:13000/api/health
```

Internal-only services should not be reachable from host published ports unless accessed through tunnel/ingress:

```bash
curl -fsS http://127.0.0.1:19090/-/ready
curl -fsS http://127.0.0.1:13100/ready
curl -fsS http://127.0.0.1:13200/ready
```

Those should fail in shared mode if the ports are not intentionally published.

From inside Grafana/Prometheus network, datasource health should still work:

```bash
docker compose exec prometheus wget -qO- http://api:8080/metrics
docker compose exec prometheus wget -qO- http://gateway:8081/metrics
```

## Implementation Phases

### Phase 1: Documentation

Status: started.

- Update `PORT.md` to mark current port table as developer-local.
- Add shared datacenter port policy.
- Add this plan.

Acceptance:

- Docs state that shared deployments should expose only ingress or gateway/auth/Grafana.
- Docs state that backing services stay internal.

### Phase 2: Shared Compose Override

Create:

```text
docker-compose.shared.yml
```

Acceptance:

- `docker compose config --quiet` passes.
- Published host ports are reduced to expected shared surface.
- Existing developer `make app-up` remains unchanged.

### Phase 3: Makefile Targets

Add:

```text
app-up-shared
app-down-shared
app-shared-ports
```

Acceptance:

- `make app-up-shared` starts the stack with reduced ports.
- `make app-up` still starts developer-local full exposure.
- `make app-shared-ports` prints only expected published ports.

### Phase 4: Ingress Option

Add optional ingress profile:

```text
docker-compose.ingress.yml
infra/nginx/tryops.conf
```

Acceptance:

- One host port can route app, auth, and Grafana.
- Keycloak public URL and OIDC issuer match the external URL.
- Grafana is protected by network policy, auth, or admin-only route.

### Phase 5: Model Serving Private Endpoint

Replace direct host FASHN endpoint with a private router abstraction:

```env
TRYOPS_REAL_VTON_URL=http://fashn-vton-router:18100
```

Acceptance:

- No model worker ports are published to the host.
- API can still run real VTON jobs.
- Grafana can see router/worker metrics through Prometheus.

### Phase 6: Observability Exporters

Add internal exporter services:

- DCGM exporter.
- node exporter.
- process exporter.
- optional cAdvisor.

Acceptance:

- Prometheus scrapes exporters by service name.
- Grafana hardware dashboard does not need public exporter ports.

## Acceptance Criteria

Shared datacenter networking is production-ready when:

- Normal users enter through one ingress endpoint or the minimal interim ports only.
- Direct FastAPI, Postgres, Valkey, MinIO, MLflow, Prometheus, Loki, Tempo, Alertmanager, OTel, guardrail, and model worker ports are not published.
- Browser OIDC login works from the public auth URL.
- Grafana works for operators and uses internal datasources.
- API reaches model serving through one private serving URL.
- Prometheus scrapes internal service names, not public host ports.
- `make app-up` remains available for developer-local debugging.
- `make app-up-shared` is the documented command for shared hosts.
- Port exposure can be verified by one command before running on a shared machine.
