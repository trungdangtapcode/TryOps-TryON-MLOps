# TryOps Ports

These are the ports used by `make app-up`. They are not always the same as the raw `docker-compose.yml` defaults because the Makefile injects local-friendly host ports.

## Port Relationship Chart

```mermaid
flowchart LR
  browser["Browser"]

  subgraph host["Host ports from make app-up"]
    h_gateway["18081<br/>Console + gateway"]
    h_api["18080<br/>FastAPI direct"]
    h_keycloak["18082<br/>Keycloak IAM"]
    h_controller["18084 -> 18082<br/>Go controller"]
    h_fashn["18101<br/>FASHN VTON service"]
    h_pg["15432<br/>Postgres"]
    h_valkey["16379<br/>Valkey"]
    h_minio_api["19000<br/>MinIO API"]
    h_minio_console["19001<br/>MinIO Console"]
    h_mlflow["15000<br/>MLflow"]
    h_prom["19090<br/>Prometheus"]
    h_alert["19093<br/>Alertmanager"]
    h_grafana["13000<br/>Grafana"]
    h_guardrail["18093<br/>Go guardrail"]
    h_otel_grpc["4317<br/>OTel gRPC"]
    h_otel_http["4318<br/>OTel HTTP"]
    h_otel_metrics["8888<br/>OTel metrics"]
    h_otel_health["13133<br/>OTel health"]
  end

  subgraph compose["Compose network"]
    gateway["gateway:8081<br/>Rust gateway"]
    api["api:8080<br/>FastAPI BFF"]
    keycloak["keycloak:8080<br/>IAM/OIDC"]
    controller["controller:18082<br/>ops webhooks"]
    postgres["postgres:5432"]
    valkey["valkey:6379"]
    minio["minio:9000/9001"]
    mlflow["mlflow:5000"]
    prometheus["prometheus:9090"]
    alertmanager["alertmanager:9093"]
    grafana["grafana:3000"]
    guardrail["guardrail:18083"]
    otel["otel-collector:4317/4318/8888/13133"]
  end

  subgraph dev["Dev-only"]
    vite_manual["15173<br/>Manual Vite dev"]
    vite_hot["18173 -> 15173<br/>Compose hot reload"]
    uvicorn["18180<br/>Manual Uvicorn"]
  end

  subgraph profiles["Profile-only"]
    tls["8443<br/>Gateway TLS profile"]
    assets["8088<br/>Web assets profile"]
  end

  browser --> h_gateway --> gateway
  browser --> h_keycloak --> keycloak
  browser --> h_controller --> controller
  browser -. manual frontend dev .-> vite_manual
  browser -. hot reload .-> vite_hot
  vite_manual --> uvicorn
  vite_hot --> gateway

  h_api --> api
  h_fashn --> fashn["host.docker.internal:18101<br/>real VTON adapter"]
  h_pg --> postgres
  h_valkey --> valkey
  h_minio_api --> minio
  h_minio_console --> minio
  h_mlflow --> mlflow
  h_prom --> prometheus
  h_alert --> alertmanager
  h_grafana --> grafana
  h_guardrail --> guardrail
  h_otel_grpc --> otel
  h_otel_http --> otel
  h_otel_metrics --> otel
  h_otel_health --> otel

  gateway --> api
  gateway --> keycloak
  gateway --> controller
  gateway --> guardrail
  gateway --> postgres
  gateway --> valkey
  api --> keycloak
  api --> fashn
  api --> mlflow
  api --> minio
  prometheus --> alertmanager
  alertmanager -. page alerts .-> controller
```

## `make app-up` Ports

| Service | Default URL or port | Override variable | Notes |
| --- | --- | --- | --- |
| TryOps Console + Rust gateway | `http://127.0.0.1:18081` | `TRYOPS_GATEWAY_PORT` | Main app URL. Use this first. |
| FastAPI backend direct | `http://127.0.0.1:18080` | `TRYOPS_API_PORT` | Direct API/docs access. Gateway normally proxies this. |
| Keycloak IAM | `http://127.0.0.1:18082` | `TRYOPS_KEYCLOAK_PORT` | OIDC/IAM service. Container port is `8080`. |
| Go controller | `http://127.0.0.1:18084` | `TRYOPS_CONTROLLER_PORT` | Webhook/control-plane service. Container port is `18082`; Alertmanager uses `http://controller:18082/alerts/webhook` inside Compose. |
| FASHN VTON service | `http://127.0.0.1:18101` | `FASHN_VTON_PORT` | Local real VTON service started by `make app-up` before Compose. API reaches it through `host.docker.internal:18101`. |
| Postgres | `127.0.0.1:15432` | `TRYOPS_POSTGRES_PORT` | Database for the full Compose stack. |
| Valkey | `127.0.0.1:16379` | `TRYOPS_VALKEY_PORT` | Hot quota/rate counter store. |
| MinIO API | `http://127.0.0.1:19000` | `TRYOPS_MINIO_PORT` | Object/artifact storage API. |
| MinIO Console | `http://127.0.0.1:19001` | `TRYOPS_MINIO_CONSOLE_PORT` | Browser UI for MinIO. |
| MLflow | `http://127.0.0.1:15000` | `TRYOPS_MLFLOW_PORT` | Experiment/model tracking. |
| Prometheus | `http://127.0.0.1:19090` | `TRYOPS_PROMETHEUS_PORT` | Metrics database. |
| Alertmanager | `http://127.0.0.1:19093` | `TRYOPS_ALERTMANAGER_PORT` | Alert routing. |
| Grafana | `http://127.0.0.1:13000` | `TRYOPS_GRAFANA_PORT` | Dashboards. Grafana defaults to `admin` / `admin` on a fresh local volume. |
| Go guardrail sidecar | `127.0.0.1:18093` | `TRYOPS_GUARDRAIL_PORT` | LLM guardrail service. Usually called by gateway/API. Container port is `18083`. |
| OpenTelemetry gRPC | `127.0.0.1:4317` | `TRYOPS_OTEL_GRPC_PORT` | OTLP gRPC receiver. |
| OpenTelemetry HTTP | `127.0.0.1:4318` | `TRYOPS_OTEL_HTTP_PORT` | OTLP HTTP receiver. |
| OpenTelemetry metrics | `127.0.0.1:8888` | `TRYOPS_OTEL_METRICS_PORT` | Collector metrics endpoint. |
| OpenTelemetry health | `127.0.0.1:13133` | `TRYOPS_OTEL_HEALTH_PORT` | Collector health endpoint. |

`make app-up` starts:

```text
FASHN VTON local service, gateway, keycloak, controller, api, postgres, valkey,
prometheus, alertmanager, otel-collector, grafana, minio, mlflow, guardrail
```

It does not start the Vite dev server unless `TRYOPS_HOT_RELOAD=1` is set.

## Development-Only Ports

| Service | Default URL or port | Override variable | Notes |
| --- | --- | --- | --- |
| Manual FastAPI dev | `http://127.0.0.1:18180` | `--port` in the `uvicorn` command | Used when running FastAPI manually for frontend development. |
| Vite frontend dev | `http://127.0.0.1:15173` | Vite may auto-pick another port if busy | Started by `npm --prefix web run dev`; not started by `make app-up`. |
| Compose hot-reload UI | `http://127.0.0.1:18173` | `TRYOPS_WEB_DEV_PORT` | Started by `make app-up-hotreload` or `make app-dev`; maps host `18173` to container Vite port `15173`. |

Frontend dev command:

```bash
VITE_TRYOPS_API_BASE=http://127.0.0.1:18180 npm --prefix web run dev
```

## Profile-Only Ports

These services are defined in Compose but are not part of the default `make app-up` service list.

| Service | Default URL or port | Override variable | Profile | Notes |
| --- | --- | --- | --- | --- |
| Web assets server | `http://127.0.0.1:8088` | `TRYOPS_WEB_ASSETS_PORT` | `assets` | Static web-assets profile. |
| Gateway TLS | `https://127.0.0.1:8443` | `TRYOPS_GATEWAY_TLS_PORT` | `tls` | Optional TLS gateway profile. |

The Go controller still has the Compose `ops` profile in `docker-compose.yml`, but `make app-up` now enables that profile and targets the controller explicitly. That means one command starts it:

```bash
make app-up
```

## Sample And Tool Ports

These ports are used by focused Makefile samples or native tools. They are not part of the default product stack.

| Service or sample | Default URL or port | Override variable | Notes |
| --- | --- | --- | --- |
| Vault live secret-rotation sample | `http://127.0.0.1:18200` | `TRYOPS_VAULT_PORT` | Used by Vault-backed secret rotation sample. |
| Native guardrail smoke | `http://127.0.0.1:18083` | `TRYOPS_GUARDRAIL_ADDR` in target | Local guardrail server used by native guardrail smoke. |
| Native Go controller smoke | `http://127.0.0.1:18082` | `TRYOPS_CONTROLLER_ADDR` in target | Local controller smoke. Conflicts with Keycloak if the product stack is running. |
| Registry webhook sample controller | `http://127.0.0.1:18084` | `TRYOPS_CONTROLLER_ADDR` in target | Local controller process used by `registry-webhook-sample`. Same host port as Compose controller profile. |
| Signed PR sample controller | `http://127.0.0.1:18085` | `TRYOPS_CONTROLLER_ADDR` in target | Local controller process used by `signed-pr-promotion-sample`. |
| Native Rust gateway smoke | `http://127.0.0.1:18086` | `TRYOPS_GATEWAY_ADDR` in target | Local Rust gateway smoke. |
| Native edge guardrail gateway | `http://127.0.0.1:18087` | `TRYOPS_GATEWAY_ADDR` in target | Gateway used by edge guardrail smoke. |
| Native edge guardrail sidecar | `http://127.0.0.1:18183` | `TRYOPS_GUARDRAIL_ADDR` in target | Guardrail sidecar used by edge guardrail smoke. |
| Native static gateway smoke | `http://127.0.0.1:18088` | `TRYOPS_GATEWAY_ADDR` in target | Static UI serving smoke. |
| Native edge cache gateway | `http://127.0.0.1:18089` | `TRYOPS_GATEWAY_ADDR` in target | Semantic-cache edge smoke. |
| Distributed quota Postgres sample | `127.0.0.1:15435` | `TRYOPS_DISTRIBUTED_QUOTA_POSTGRES_PORT` | Temporary Postgres host port for distributed quota admission smoke. |
| Distributed quota gateway A | `http://127.0.0.1:18101` | hardcoded in sample | Temporary Rust gateway for distributed quota smoke. Conflicts with FASHN VTON if both run at once. |
| Distributed quota gateway B | `http://127.0.0.1:18102` | hardcoded in sample | Temporary Rust gateway for distributed quota smoke. |
| Native full-stack load gateway | `http://127.0.0.1:18221` | `TRYOPS_FULLSTACK_LOAD_GATEWAY_PORT` | Used by `native-fullstack-load` tooling. |
| Native full-stack load Python API | `http://127.0.0.1:18222` | `TRYOPS_FULLSTACK_LOAD_PYTHON_PORT` | Used by `native-fullstack-load` tooling. |

## Raw Compose Defaults

If you run `docker compose up` directly without the Makefile-provided environment variables, these host ports are different:

| Service | Raw Compose default | `make app-up` default |
| --- | --- | --- |
| Postgres | `5432` | `15432` |
| Keycloak | `18082` | `18082` |
| MinIO API | `9000` | `19000` |
| MinIO Console | `9001` | `19001` |
| MLflow | `5000` | `15000` |
| Prometheus | `9090` | `19090` |
| Alertmanager | `9093` | `19093` |
| Grafana | `3000` | `13000` |
| Go guardrail | `18083` | `18093` |
| FastAPI backend | `8080` | `18080` |
| Rust gateway | `8081` | `18081` |
| Go controller | `18084` | `18084` |
| Compose hot-reload Vite | `18173` | Hot-reload only |
