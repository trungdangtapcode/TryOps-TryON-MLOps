# TryOps

TryOps is an MLOps product stack for virtual try-on, optimized LLM serving, quota enforcement, guardrails, governance evidence, and production operations.

The repo is native-first at the product boundary: a Rust gateway protects the edge, a Python FastAPI backend coordinates product workflows, Go services handle platform/control-plane concerns, and C++ CLIs cover deterministic hot paths.

## Quick Start

Start the local product stack:

```bash
make app-up
```

Open the Console:

```text
http://127.0.0.1:18081
```

Use a demo API key:

```text
tryops-viewer-demo-key
```

Check the stack:

```bash
curl -fsS http://127.0.0.1:18081/api/health
make app-smoke
```

Stop it:

```bash
make app-down
```

### Real VTON Model

The production VTON target uses the open-source FASHN VTON v1.5 model. It runs as a host GPU service, then the Docker app calls it through `host.docker.internal`.

One-time setup:

```bash
make fashn-vton-download
```

Start the model service in one terminal:

```bash
make fashn-vton-service
```

This binds the model service on port `18101` so Docker can reach it through `host.docker.internal`.

Start the app in another terminal:

```bash
make app-up
```

Then open `http://127.0.0.1:18081`, enter `tryops-viewer-demo-key`, go to VTON Studio, upload a person image and garment image, keep `FASHN VTON 1.5 GPU` selected, and press Run. The generated image is saved to the output path shown in the UI, usually `artifacts/runtime/vton/console-output.png`.

Quick local model check without the app:

```bash
make fashn-vton-sample
```

For frontend development:

```bash
python -m pip install -e ".[dev]"
make db-init
PYTHONPATH=src python -m uvicorn tryops.api:create_app --factory --host 0.0.0.0 --port 18180
```

In another terminal:

```bash
npm --prefix web ci
VITE_TRYOPS_API_BASE=http://127.0.0.1:18180 npm --prefix web run dev
```

Open `http://127.0.0.1:15173`.

## Architecture

```mermaid
flowchart LR
  user["Browser Console<br/>React + Vite"] --> gateway["Rust Gateway<br/>Axum edge"]
  gateway --> api["FastAPI BFF<br/>Python product API"]
  gateway --> guardrail["Go Guardrail<br/>LLM safety"]
  gateway --> quota[(Postgres<br/>quota ledger)]
  gateway --> valkey[(Valkey<br/>hot counters)]

  api --> workflows["Product workflows<br/>LLM, VTON, eval, governance"]
  api --> mlflow["MLflow<br/>tracking"]
  api --> minio[(MinIO<br/>artifacts)]
  api --> dvc["DVC<br/>data versions"]
  api --> native["Native tools<br/>Go, C++, Rust"]

  gateway --> otel["OpenTelemetry<br/>logs + traces"]
  gateway --> prometheus["Prometheus<br/>metrics"]
  prometheus --> alertmanager["Alertmanager"]
  prometheus --> grafana["Grafana"]
```

Main responsibilities:

- `web/`: React Console for operators, admins, risk, and demo users.
- `native/rust/tryops-gateway`: edge gateway, static UI serving, auth preflight, quota, rate limits, payload limits, proxying, metrics, tracing, and semantic-cache admission.
- `src/tryops/`: FastAPI BFF, product API, model adapters, deterministic fallbacks, governance, evaluation, orchestration, and evidence helpers.
- `native/go/`: guardrail service, controllers, job runners, load tools, quota read models, CI/config/supply-chain contracts.
- `native/cpp/`: deterministic policy, metrics, image, VTON, LLM, cache, SLO, and evaluation CLIs.
- `infra/`: local observability, Postgres migrations, Kubernetes examples, backup and alerting assets.

## Tech Stack

- Frontend: React, Vite, TypeScript, lucide-react.
- API/BFF: Python 3.11+, FastAPI, Pydantic, Uvicorn.
- ML/MLOps: MLflow, DVC, Evidently, optional PyTorch/Transformers/Diffusers/vLLM.
- Edge/runtime: Rust, Axum, Tokio.
- Platform tools: Go.
- Native hot paths: C++17.
- Data/services: Postgres, Valkey, MinIO.
- Observability: OpenTelemetry, Prometheus, Alertmanager, Grafana.
- Local runtime: Docker Compose, Makefile targets, JSON contracts.

## Data Flow

```mermaid
sequenceDiagram
  participant User
  participant Console as React Console
  participant Gateway as Rust Gateway
  participant Guardrail as Go Guardrail
  participant API as FastAPI BFF
  participant Tools as Models + Native Tools
  participant Evidence as Artifacts + Reports
  participant Obs as Observability

  User->>Console: Open app
  Console->>Gateway: /api/* with API key
  Gateway->>Gateway: Auth, limits, quota, tracing
  Gateway->>Guardrail: Safety check when needed
  Guardrail-->>Gateway: Allow or block
  Gateway->>API: Proxy accepted request as /v1/*
  API->>Tools: Run LLM, VTON, eval, governance workflow
  Tools-->>API: Result or deterministic fallback
  API->>Evidence: Write local evidence
  Gateway->>Obs: Emit logs, traces, metrics
  API-->>Gateway: Product response
  Gateway-->>Console: Response
  Console-->>User: Dashboard or workflow result
```

Summary:

1. Console sends `/api/*` requests through the gateway.
2. Gateway enforces auth, limits, quota, tracing, and guardrails.
3. FastAPI runs product workflows and calls model/native paths.
4. Evidence lands in `artifacts/` and `reports/generated/`.
5. Observability flows to OpenTelemetry, Prometheus, and Grafana.

## Project Flow

Typical development loop:

```mermaid
flowchart TD
  edit["Edit code/config<br/>web, src/tryops, native, configs, contracts"]
  tests["Run focused tests<br/>Python, web, Rust, Go, C++"]
  samples["Run product samples<br/>LLM, VTON, quota, guardrails"]
  evidence["Generate evidence<br/>artifacts and reports"]
  smoke["Smoke full stack<br/>make app-smoke"]

  edit --> tests --> samples --> evidence --> smoke
```

Useful commands:

```bash
make test
make web-typecheck
make native-rust-test
make native-go-test
make native-cpp-test
make app-smoke
```

Common sample flows:

```bash
make vton-baseline-sample
make llm-benchmark-sample
make guardrail-sample
make quota-sample
make pipeline-sample
make deploy-package-sample
```

Real model runs are optional and need ML extras plus suitable hardware:

```bash
python -m pip install -e ".[dev,ml]"
make fashn-vton-download
make fashn-vton-service
make llm-real-sample
```

## Repository Map

```text
web/                 React/Vite Console
src/tryops/          FastAPI app, pipelines, adapters, product logic
native/rust/         Rust gateway
native/go/           Go services and operational tools
native/cpp/          C++ deterministic CLIs
infra/               Observability, migrations, deployment assets
configs/             Runtime and policy config
contracts/           JSON schemas
samples/             Demo inputs and candidate payloads
scripts/             Automation and evidence generation
tests/               Python contract tests
docs/                Detailed architecture and operations notes
artifacts/           Generated local outputs, ignored by Git
reports/generated/   Generated cards/reports, ignored by Git
```



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


## Main Ports

When using `make app-up`:

```text
Console + gateway: http://127.0.0.1:18081
FastAPI direct:    http://127.0.0.1:18080
FASHN VTON model:  http://127.0.0.1:18101
Grafana:           http://127.0.0.1:13000
Prometheus:        http://127.0.0.1:19090
MLflow:            http://127.0.0.1:15000
MinIO API:         http://127.0.0.1:19000
MinIO Console:     http://127.0.0.1:19001
```

If port `18101` conflicts, start the model service on another port and point the app at it:

```bash
FASHN_VTON_PORT=18111 make fashn-vton-service
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18111 make app-up
```

## Deeper Docs

- Architecture: `docs/architecture.md`
- API contract: `docs/api_contract.md`
- Production app plan: `docs/production_app_plan.md`
- Orchestration: `docs/orchestration.md`
- Observability: `docs/observability_contract.md`
- Supply chain: `docs/supply_chain.md`
- Native modules: `native/README.md`
