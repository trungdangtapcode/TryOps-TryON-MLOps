# TryOps Ports

These are the ports used by `make app-up`. They are not always the same as the raw `docker-compose.yml` defaults because the Makefile injects local-friendly host ports.

## Port Relationship Chart

```mermaid
flowchart LR
  browser["Browser"]

  subgraph host["Host ports from make app-up"]
    h_gateway["18081<br/>Console + gateway"]
    h_api["18080<br/>FastAPI direct"]
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
    postgres["postgres:5432"]
    valkey["valkey:6379"]
    minio["minio:9000/9001"]
    mlflow["mlflow:5000"]
    prometheus["prometheus:9090"]
    alertmanager["alertmanager:9093"]
    grafana["grafana:3000"]
    guardrail["guardrail:18083"]
    otel["otel-collector:4317/4318"]
  end

  subgraph dev["Dev-only"]
    vite["15173<br/>Vite dev server"]
    uvicorn["18180<br/>Manual Uvicorn"]
  end

  subgraph profiles["Profile-only"]
    controller["18082<br/>Go controller ops profile"]
    tls["8443<br/>Gateway TLS profile"]
    assets["8088<br/>Web assets profile"]
  end

  browser --> h_gateway --> gateway
  browser -. frontend dev .-> vite
  vite --> uvicorn

  h_api --> api
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
  gateway --> guardrail
  gateway --> postgres
  gateway --> valkey
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
gateway, api, postgres, valkey, prometheus, alertmanager, otel-collector,
grafana, minio, mlflow, guardrail
```

It does not start the Vite dev server or the Go controller.

## Development-Only Ports

| Service | Default URL or port | Override variable | Notes |
| --- | --- | --- | --- |
| Manual FastAPI dev | `http://127.0.0.1:18180` | `--port` in the `uvicorn` command | Used when running FastAPI manually for frontend development. |
| Vite frontend dev | `http://127.0.0.1:15173` | Vite may auto-pick another port if busy | Started by `npm --prefix web run dev`; not started by `make app-up`. |

Frontend dev command:

```bash
VITE_TRYOPS_API_BASE=http://127.0.0.1:18180 npm --prefix web run dev
```

## Profile-Only Ports

These services are defined in Compose but are not part of the default `make app-up` service list.

| Service | Default URL or port | Override variable | Profile | Notes |
| --- | --- | --- | --- | --- |
| Go controller | `127.0.0.1:18082` | `TRYOPS_CONTROLLER_PORT` | `ops` | Handles `/health`, `/reconcile`, `/registry/webhook`, `/github/pr-webhook`, and `/alerts/webhook`. Alertmanager page alerts target `http://controller:18082/alerts/webhook` inside the Compose network. |
| Web assets server | `http://127.0.0.1:8088` | `TRYOPS_WEB_ASSETS_PORT` | `assets` | Static web-assets profile. |
| Gateway TLS | `https://127.0.0.1:8443` | `TRYOPS_GATEWAY_TLS_PORT` | `tls` | Optional TLS gateway profile. |

Start the controller profile when testing Alertmanager webhook delivery:

```bash
docker compose --profile ops up --build -d controller alertmanager prometheus
```

## Raw Compose Defaults

If you run `docker compose up` directly without the Makefile-provided environment variables, these host ports are different:

| Service | Raw Compose default | `make app-up` default |
| --- | --- | --- |
| Postgres | `5432` | `15432` |
| MinIO API | `9000` | `19000` |
| MinIO Console | `9001` | `19001` |
| MLflow | `5000` | `15000` |
| Prometheus | `9090` | `19090` |
| Alertmanager | `9093` | `19093` |
| Grafana | `3000` | `13000` |
| FastAPI backend | `8080` | `18080` |
| Rust gateway | `8081` | `18081` |
