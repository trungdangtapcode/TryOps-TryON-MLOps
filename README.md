# TryOps

TryOps is an MLOps product stack for AI virtual try-on, LLM-assisted product workflows, account quota, IAM, observability, model serving, and operational dashboards.

The local stack is designed around one command, but it still expects model endpoint configuration. `make app-up` starts the product stack, prepares the FASHN VTON runtime, starts the host-side VTON router, and then brings up the Docker Compose services.

## Tech Stack

<table>
  <tr>
    <th align="left">Frontend</th>
    <td>
      <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=061421" alt="React">
      <img src="https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
      <img src="https://img.shields.io/badge/Vite-7-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite">
      <img src="https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
      <img src="https://img.shields.io/badge/Lucide_React-icons-F56565?style=for-the-badge&logo=lucide&logoColor=white" alt="Lucide React">
    </td>
  </tr>
  <tr>
    <th align="left">Backend / Server</th>
    <td>
      <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
      <img src="https://img.shields.io/badge/FastAPI-BFF-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
      <img src="https://img.shields.io/badge/Axum-0.8-2E3440?style=for-the-badge&logo=rust&logoColor=white" alt="Axum">
      <img src="https://img.shields.io/badge/Tokio-1-2E3440?style=for-the-badge&logo=rust&logoColor=white" alt="Tokio">
      <img src="https://img.shields.io/badge/Tower_HTTP-0.6-2E3440?style=for-the-badge&logo=rust&logoColor=white" alt="Tower HTTP">
      <img src="https://img.shields.io/badge/Reqwest-0.12-2E3440?style=for-the-badge&logo=rust&logoColor=white" alt="Reqwest">
      <img src="https://img.shields.io/badge/Rustls-0.23-2E3440?style=for-the-badge&logo=rust&logoColor=white" alt="Rustls">
      <img src="https://img.shields.io/badge/Serde-1-2E3440?style=for-the-badge&logo=rust&logoColor=white" alt="Serde">
      <img src="https://img.shields.io/badge/Tracing-0.1-2E3440?style=for-the-badge&logo=rust&logoColor=white" alt="Tracing">
      <img src="https://img.shields.io/badge/Tokio_Postgres-0.7-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="Tokio Postgres">
      <img src="https://img.shields.io/badge/Go-services-00ADD8?style=for-the-badge&logo=go&logoColor=white" alt="Go">
      <img src="https://img.shields.io/badge/x%2Fimage-demo_recorder-00ADD8?style=for-the-badge&logo=go&logoColor=white" alt="golang.org/x/image">
      <img src="https://img.shields.io/badge/net%2Fhttp-standard_library-00ADD8?style=for-the-badge&logo=go&logoColor=white" alt="Go net/http">
      <img src="https://img.shields.io/badge/encoding%2Fjson-standard_library-00ADD8?style=for-the-badge&logo=go&logoColor=white" alt="Go encoding/json">
      <img src="https://img.shields.io/badge/pgx%2Fpgxpool-v5-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="pgx pgxpool">
      <img src="https://img.shields.io/badge/yaml.v3-config_contracts-CB171E?style=for-the-badge&logo=yaml&logoColor=white" alt="yaml.v3">
      <img src="https://img.shields.io/badge/C%2B%2B17-native_tools-00599C?style=for-the-badge&logo=cplusplus&logoColor=white" alt="C++17">
      <img src="https://img.shields.io/badge/C%2B%2B17-STL-00599C?style=for-the-badge&logo=cplusplus&logoColor=white" alt="C++17 STL">
      <img src="https://img.shields.io/badge/GCC%2Fg%2B%2B-native_build-2E3440?style=for-the-badge&logo=gnu&logoColor=white" alt="GCC g++">
      <img src="https://img.shields.io/badge/Makefile-build_targets-427819?style=for-the-badge&logo=gnu&logoColor=white" alt="Makefile build targets">
      <img src="https://img.shields.io/badge/regex%2Fchrono%2Ffilesystem-STL_modules-00599C?style=for-the-badge&logo=cplusplus&logoColor=white" alt="C++ standard library modules">
      <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
      <img src="https://img.shields.io/badge/Rust-gateway-000000?style=for-the-badge&logo=rust&logoColor=white" alt="Rust">
    </td>
  </tr>
  <tr>
    <th align="left">AI / ML Stack</th>
    <td>
      <img src="https://img.shields.io/badge/PyTorch-GPU_inference-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch">
      <img src="https://img.shields.io/badge/Hugging_Face-model_hub-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" alt="Hugging Face">
      <img src="https://img.shields.io/badge/FASHN_VTON-1.5-111111?style=for-the-badge" alt="FASHN VTON">
      <img src="https://img.shields.io/badge/OpenAI_API-compatible-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI API">
      <img src="https://img.shields.io/badge/vLLM-local_serving-76B900?style=for-the-badge" alt="vLLM">
    </td>
  </tr>
  <tr>
    <th align="left">Ops Stack</th>
    <td>
      <img src="https://img.shields.io/badge/Prometheus-metrics-E6522C?style=for-the-badge&logo=prometheus&logoColor=white" alt="Prometheus">
      <img src="https://img.shields.io/badge/Grafana-dashboards-F46800?style=for-the-badge&logo=grafana&logoColor=white" alt="Grafana">
      <img src="https://img.shields.io/badge/MLflow-tracking-0194E2?style=for-the-badge&logo=mlflow&logoColor=white" alt="MLflow">
      <img src="https://img.shields.io/badge/HAProxy-optional_edge_LB-106DA9?style=for-the-badge&logo=haproxy&logoColor=white" alt="HAProxy load balancer">
      <img src="https://img.shields.io/badge/DVC-data_versioning-13ADC7?style=for-the-badge&logo=dvc&logoColor=white" alt="DVC">
      <img src="https://img.shields.io/badge/MinIO-artifact_store-C72E49?style=for-the-badge&logo=minio&logoColor=white" alt="MinIO">
      <img src="https://img.shields.io/badge/Valkey-8-DC382D?style=for-the-badge&logo=valkey&logoColor=white" alt="Valkey">
      <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Compose">
      <img src="https://img.shields.io/badge/Kubernetes-manifests-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white" alt="Kubernetes manifests">
      <img src="https://img.shields.io/badge/Loki-logs-F46800?style=for-the-badge&logo=grafana&logoColor=white" alt="Loki">
      <img src="https://img.shields.io/badge/Tempo-traces-F46800?style=for-the-badge&logo=grafana&logoColor=white" alt="Tempo">
      <img src="https://img.shields.io/badge/OpenTelemetry-OTLP-000000?style=for-the-badge&logo=opentelemetry&logoColor=white" alt="OpenTelemetry">
      <img src="https://img.shields.io/badge/Alertmanager-alerts-E6522C?style=for-the-badge&logo=prometheus&logoColor=white" alt="Alertmanager">
      <img src="https://img.shields.io/badge/Keycloak-IAM-4D4D4D?style=for-the-badge&logo=keycloak&logoColor=white" alt="Keycloak">
    </td>
  </tr>
</table>

## Visual Overview

### Product Screenshots

| Console | Try-on run |
| --- | --- |
| ![TryOps main page](report/assets/screenshots/main-page.png) | ![TryOps example run](report/assets/screenshots/example-run.png) |

| Workspace | Keycloak IAM |
| --- | --- |
| ![Workspace](report/assets/screenshots/workspace.png) | ![Keycloak IAM](report/assets/screenshots/keycloak.png) |

| Grafana | Log drilldown |
| --- | --- |
| ![Grafana dashboards](report/assets/screenshots/grafana.png) | ![Log drilldown](report/assets/screenshots/log-drilldown.png) |

| MLflow | MinIO |
| --- | --- |
| ![MLflow](report/assets/screenshots/mlflow.png) | ![MinIO](report/assets/screenshots/minIO.png) |

### CI/CD Pipeline

<p>
  <img src="https://img.shields.io/badge/GitHub_Actions-CI%2FCD-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions">
  <img src="https://img.shields.io/badge/Docker_Buildx-image_builds-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Buildx">
  <img src="https://img.shields.io/badge/GHCR-container_registry-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Container Registry">
  <img src="https://img.shields.io/badge/Syft-SBOM-5B45B1?style=for-the-badge" alt="Syft SBOM">
  <img src="https://img.shields.io/badge/Trivy-HIGH%2FCRITICAL_gate-1904DA?style=for-the-badge&logo=trivy&logoColor=white" alt="Trivy scan gate">
  <img src="https://img.shields.io/badge/Cosign-keyless_signing-3C3C3D?style=for-the-badge&logo=sigstore&logoColor=white" alt="Cosign keyless signing">
</p>

The project includes a GitHub Actions workflow at [.github/workflows/ci.yml](.github/workflows/ci.yml). It runs on pull requests, pushes to `main` / `production`, and manual dispatches.

```mermaid
flowchart LR
  trigger["PR / main / production / manual"] --> local_ci["Local CI<br/>Python, web, Go, Rust, C++"]
  local_ci --> contracts["Contracts<br/>Compose, containers, secrets, incidents"]
  contracts --> evidence["Evaluation artifacts<br/>artifacts/eval + reports/generated"]

  trigger --> images["Image matrix<br/>gateway, controller, guardrail, benchmark,<br/>cpp-tools, api, web-assets"]
  images --> sbom["SBOM<br/>Syft SPDX"]
  sbom --> scan["Security gate<br/>Trivy HIGH / CRITICAL"]
  scan --> sign["Non-PR release<br/>GHCR push + Cosign OIDC signing"]
  sign --> artifacts["CI artifacts<br/>SBOM, scan, signatures"]
```

| Stage | Coverage |
| --- | --- |
| Test and build | Python contracts, React typecheck/build, native Go tests, Rust gateway tests, and C++ native tests. |
| Runtime contracts | Docker Compose validation, container contract checks, dependency lock, secret rotation, and incident workflow checks. |
| Supply chain | SBOM generation, vulnerability scan reports, CI contract validation, and uploaded evaluation artifacts. |
| Image pipeline | Builds seven container roles with Docker Buildx: gateway, controller, guardrail, benchmark, cpp-tools, api, and web-assets. |
| Release security | Pushes images to GHCR on non-PR runs, emits build provenance/SBOM, and signs release images with Cosign keyless OIDC. |

### Runtime Architecture

```mermaid
flowchart LR
  browser["Browser<br/>TryOps Console"] --> gateway["Rust Gateway<br/>auth, quota, proxy"]
  gateway --> api["FastAPI BFF<br/>product workflows"]
  gateway --> guardrail["Go Guardrail<br/>policy checks"]

  api --> postgres[(Postgres<br/>accounts, jobs, quota)]
  api --> valkey[(Valkey<br/>hot counters)]
  api --> minio[(MinIO<br/>artifacts)]
  api --> mlflow["MLflow<br/>experiments"]
  api --> vton["FASHN VTON Router<br/>GPU workers"]
  api --> llm["OpenAI-compatible LLM<br/>OpenAI or vLLM"]

  gateway --> otel["OpenTelemetry"]
  api --> otel
  vton --> otel
  otel --> loki["Loki logs"]
  otel --> tempo["Tempo traces"]
  gateway --> prometheus["Prometheus metrics"]
  prometheus --> grafana["Grafana dashboards"]
  loki --> grafana
  tempo --> grafana
```

### C4 Context

```mermaid
flowchart LR
  professor["Professor / Evaluator<br/>reviews UI, metrics, reports"]
  ml_engineer["ML Engineer<br/>runs experiments and evaluation"]
  risk_owner["Risk Owner<br/>reviews operational risk"]

  tryops["TryOps Platform<br/>MLOps control plane for VTON and LLM workflows"]

  vton["VTON Models<br/>FASHN VTON runtime"]
  llm["LLM Runtime<br/>OpenAI-compatible API or vLLM"]
  mlflow["MLflow<br/>tracking and registry"]
  minio["MinIO<br/>artifact storage"]
  grafana["Grafana / Prometheus<br/>metrics and dashboards"]

  professor --> tryops
  ml_engineer --> tryops
  risk_owner --> tryops
  tryops --> vton
  tryops --> llm
  tryops --> mlflow
  tryops --> minio
  tryops --> grafana
```

### Container View

```mermaid
flowchart TB
  user["User / Operator"]

  subgraph tryops["TryOps"]
    ui["React / Vite Console"]
    gateway["Rust Axum Gateway<br/>auth, quota, validation, proxy"]
    api["FastAPI BFF<br/>product APIs and jobs"]
    guardrail["Go Guardrail<br/>policy checks"]
    postgres[(Postgres<br/>accounts, jobs, quota)]
    valkey[(Valkey<br/>hot counters)]
    minio[(MinIO<br/>artifacts)]
    mlflow["MLflow<br/>experiments"]
    vton["FASHN VTON Router<br/>GPU workers"]
    llm["LLM Endpoint<br/>OpenAI-compatible"]
    obs["Prometheus / Grafana / Loki / Tempo / OTel"]
  end

  user --> ui
  ui --> gateway
  gateway --> api
  gateway --> guardrail
  gateway --> postgres
  gateway --> valkey
  api --> postgres
  api --> minio
  api --> mlflow
  api --> vton
  api --> llm
  gateway --> obs
  api --> obs
  vton --> obs
```

### Developer-Local Service Topology

![Developer-local service topology](report/assets/port-service-diagram.png)

### FASHN VTON Model Flow

![FASHN VTON model flow](report/assets/fashn-vton-diagram.jpg)

## Requirements

- Linux workstation or server with Docker and Docker Compose.
- Python 3.12 for the host-side FASHN VTON virtual environment.
- NVIDIA driver and CUDA-capable GPU for FASHN VTON inference.
- Internet access on first run for Docker images, Python packages, FASHN source, and model weights.
- One LLM endpoint:
  - OpenAI API, or
  - a local OpenAI-compatible server such as vLLM.

## Quick Start

```bash
git clone <repo-url>
cd mlops
cp .env.example .env
```

Edit `.env` and configure the LLM section.

For local vLLM:

```bash
vllm serve HuggingFaceTB/SmolLM2-135M-Instruct --host 127.0.0.1 --port 8000
```

```env
TRYOPS_LLM_BASE_URL=http://host.docker.internal:8000/v1
TRYOPS_LLM_MODEL=HuggingFaceTB/SmolLM2-135M-Instruct
TRYOPS_LLM_API_KEY=
```

Keep the VTON defaults unless you need a different GPU:

```env
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100
TRYOPS_FASHN_GPU_IDS=0
TRYOPS_FASHN_REQUIRE_CUDA=1
TRYOPS_FASHN_ALLOW_CPU_FALLBACK=0
```

Start the stack:

```bash
make app-up
```

Open the app:

```text
http://127.0.0.1:18081
```

The first run can take a long time because it creates the FASHN Python environment and downloads model weights. Later runs reuse cached artifacts under `artifacts/`.

## Accounts

Use the TryOps UI to sign up or sign in through Keycloak. The API creates a workspace account automatically after the first login.

Local Keycloak admin:

```text
URL:      http://127.0.0.1:18082
Username: tryops-admin
Password: tryops-local-keycloak
```

## Common Commands

| Command | Purpose |
| --- | --- |
| `make app-up` | Start the product stack and model-serving helpers. |
| `make app-down` | Stop Compose services and host-side model helpers. |
| `make app-smoke` | Check stack readiness through the gateway. |
| `make app-up-hotreload` | Start the app with React/FastAPI hot reload. |
| `make web-typecheck` | Type-check the React frontend. |
| `make native-rust-test` | Test the Rust gateway. |
| `make native-go-test` | Test Go services and tools. |
| `make native-cpp-test` | Test C++ native tools. |
| `make fashn-vton-workers-status` | Inspect the FASHN router and GPU workers. |

Hot reload UI:

```text
http://127.0.0.1:18173
```

## Main Local URLs

| Service | Default URL or port | Override variable | Notes |
| --- | --- | --- | --- |
| TryOps Console + Rust gateway | `http://127.0.0.1:18081` | `TRYOPS_GATEWAY_PORT` | Main app URL. Use this first. |
| FastAPI backend direct | `http://127.0.0.1:18080` | `TRYOPS_API_PORT` | Direct API/docs access. Gateway normally proxies this. |
| Keycloak IAM | `http://127.0.0.1:18082` | `TRYOPS_KEYCLOAK_PORT` | OIDC/IAM service. Container port is `8080`. |
| Go controller | `http://127.0.0.1:18084` | `TRYOPS_CONTROLLER_PORT` | Webhook/control-plane service. Container port is `18082`; Alertmanager uses `http://controller:18082/alerts/webhook` inside Compose. |
| FASHN VTON router | `http://127.0.0.1:18100` | `FASHN_VTON_ROUTER_PORT` | Host-side real VTON router started by `make app-up` before Compose. This is not a Docker Compose container. API reaches it from inside Docker through `host.docker.internal:18100`. |
| FASHN VTON single-worker debug | `http://127.0.0.1:18101` | `FASHN_VTON_PORT` | Optional direct service for isolated debugging with `make fashn-vton-service-bg`. `make app-up` does not use it. |
| Optional local vLLM/OpenAI-compatible LLM | `http://127.0.0.1:8000/v1` | `VLLM_PORT`, `VLLM_BASE_URL`, `TRYOPS_LLM_BASE_URL` | Host-side real LLM endpoint used only when self-hosting vLLM. If `TRYOPS_LLM_BASE_URL=https://api.openai.com/v1`, no local LLM port is needed. |
| Postgres | `127.0.0.1:15432` | `TRYOPS_POSTGRES_PORT` | Database for the full Compose stack. |
| Valkey | `127.0.0.1:16379` | `TRYOPS_VALKEY_PORT` | Hot quota/rate counter store. |
| MinIO API | `http://127.0.0.1:19000` | `TRYOPS_MINIO_PORT` | Object/artifact storage API. |
| MinIO Console | `http://127.0.0.1:19001` | `TRYOPS_MINIO_CONSOLE_PORT` | Browser UI for MinIO. |
| MLflow | `http://127.0.0.1:15000` | `TRYOPS_MLFLOW_PORT` | Experiment/model tracking. |
| Prometheus | `http://127.0.0.1:19090` | `TRYOPS_PROMETHEUS_PORT` | Metrics database. |
| Alertmanager | `http://127.0.0.1:19093` | `TRYOPS_ALERTMANAGER_PORT` | Alert routing. |
| Grafana | `http://127.0.0.1:13000` | `TRYOPS_GRAFANA_PORT` | Dashboards. Grafana defaults to `admin` / `admin` on a fresh local volume. |
| Loki | `http://127.0.0.1:13100` | `TRYOPS_LOKI_PORT` | Log store used by Grafana when `TRYOPS_OBSERVABILITY` is enabled. Container port is `3100`. |
| Tempo | `http://127.0.0.1:13200` | `TRYOPS_TEMPO_PORT` | Trace store used by Grafana when `TRYOPS_OBSERVABILITY` is enabled. Container port is `3200`. |
| Go guardrail sidecar | `127.0.0.1:18093` | `TRYOPS_GUARDRAIL_PORT` | LLM guardrail service. Usually called by gateway/API. Container port is `18083`. |
| OpenTelemetry gRPC | `127.0.0.1:4317` | `TRYOPS_OTEL_GRPC_PORT` | OTLP gRPC receiver. |
| OpenTelemetry HTTP | `127.0.0.1:4318` | `TRYOPS_OTEL_HTTP_PORT` | OTLP HTTP receiver. |
| OpenTelemetry metrics | `127.0.0.1:8888` | `TRYOPS_OTEL_METRICS_PORT` | Collector metrics endpoint. |
| OpenTelemetry health | `127.0.0.1:13133` | `TRYOPS_OTEL_HEALTH_PORT` | Collector health endpoint. |
| OTel bridge metrics | `http://127.0.0.1:19122/metrics` | `TRYOPS_OTEL_BRIDGE_PORT` | Bridges local TryOps JSONL logs/traces into OTLP for Grafana/Loki/Tempo. |

Grafana defaults to `admin` / `admin` on a fresh local volume. MinIO uses `TRYOPS_MINIO_ROOT_USER` and `TRYOPS_MINIO_ROOT_PASSWORD` from `.env`.

## Observability

`make app-up` enables the observability profile by default. Grafana includes dashboards for:

- API and gateway health.
- VTON job lifecycle.
- FASHN router and worker logs.
- `TRYOPS_REAL_VTON_URL` calls from the API.
- Prometheus metrics.
- Loki logs.
- Tempo traces.

Useful local files:

```text
artifacts/logs/fashn-vton-router.log
artifacts/logs/fashn_vton_router_events.jsonl
artifacts/logs/fashn_vton_events.jsonl
```

## Repository Map

| Path | Purpose |
| --- | --- |
| `web/` | React/Vite TryOps Console. |
| `src/tryops/` | FastAPI BFF, product APIs, model adapters, jobs, and workflow logic. |
| `native/rust/` | Rust gateway and edge runtime. |
| `native/go/` | Guardrail service, controllers, job tools, and operational utilities. |
| `native/cpp/` | Native command-line tools for policy, metrics, eval, and performance paths. |
| `configs/` | Runtime and policy configuration. |
| `contracts/` | JSON schemas and service contracts. |
| `docs/` | Architecture and operations notes. |
| `infra/` | Observability, deployment, and migration assets. |
| `scripts/` | Automation, benchmarks, model-serving helpers, and report tooling. |
| `tests/` | Python contract and integration tests. |
| `report/` | Final report assets, screenshots, diagrams, and generated PDFs. |
| `artifacts/` | Local generated outputs and model/runtime caches. |

## Troubleshooting

If `make app-up` stops at the LLM check, set `TRYOPS_LLM_BASE_URL`, `TRYOPS_LLM_MODEL`, and `TRYOPS_LLM_API_KEY`, or start a local vLLM server.

If FASHN weight download fails because of Hugging Face cache permissions, keep these values in `.env`:

```env
HF_HOME=artifacts/hf-home
HF_HUB_CACHE=artifacts/hf-home/hub
HF_XET_CACHE=artifacts/hf-home/xet
HF_HUB_DISABLE_XET=1
XDG_CACHE_HOME=artifacts/cache/xdg
TMPDIR=artifacts/cache/tmp
```

If GPU workers do not start, check:

```bash
nvidia-smi
make fashn-vton-workers-status
tail -100 artifacts/logs/fashn-vton-router.log
```
