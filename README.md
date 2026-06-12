# TryOps

Enterprise open-source MLOps product for Virtual Try-On, optimized LLM serving, quota enforcement, native guardrails, governance evidence, and production operations.

The repo is intentionally native-first at the production boundary:

- Rust: Axum gateway, static UI serving, auth preflight, quota/rate/payload gates, trace propagation, semantic-cache admission.
- Go: controllers, guardrail sidecar, job runner, load driver, CI/supply-chain contracts, runtime evidence tools.
- C++: deterministic hot-path CLIs for policy, image metrics, experiment routing/stats, cache, SLO/perf, VTON preprocessing/eval, lineage and manifest checks.
- Python: FastAPI product BFF, model adapters, deterministic fallbacks, orchestration glue, contract tests.
- React/Vite/TypeScript: browser Console under `web/`.

## Requirements

Install these first:

- Docker Engine with Docker Compose v2
- Python 3.11 or 3.12
- Node.js 20+ and npm
- Go 1.22+; `make native-go-toolchain` downloads the pinned `go1.25.5` wrapper used by this repo
- Rust/Cargo through rustup
- `g++` with C++17 support
- `make`, `curl`, and `git`

Optional for real model paths:

- CUDA GPU plus the Python `.[ml]` extras for real diffusion VTON and real LLM runs
- `syft`, `trivy`, and `cosign`, or Docker access so the live supply-chain targets can run their pinned container images
- `vllm`, KServe, Vault, k6, Locust, and external observability services for production-profile extensions

## First Setup

From the repo root:

```bash
python -m pip install -e ".[dev]"
npm --prefix web ci
make native-go-toolchain
make native-tooling
```

Optional local secrets:

```bash
cp .env.example .env
```

`make app-up` already supplies safe local defaults, so `.env` is only needed when you want to override credentials, ports, TLS material, or provider keys.

## Run The Product Stack

Start the local product stack through Docker Compose:

```bash
make app-up
```

Open these URLs:

- Console through the Rust gateway: `http://127.0.0.1:18081`
- FastAPI docs direct: `http://127.0.0.1:18080/api/docs`
- Grafana: `http://127.0.0.1:13000`
- Prometheus: `http://127.0.0.1:19090`
- MLflow: `http://127.0.0.1:15000`
- MinIO API: `http://127.0.0.1:19000`
- MinIO Console: `http://127.0.0.1:19001`

Demo API keys for the Console session field:

```text
tryops-viewer-demo-key
tryops-operator-demo-key
tryops-admin-demo-key
tryops-risk-demo-key
```

Stop the stack:

```bash
make app-down
```

Remove local Compose volumes too:

```bash
docker compose down --volumes --remove-orphans
```

## Smoke Test The Stack

Run a disposable full-stack smoke test. It builds the stack, verifies gateway/API/product evidence paths, runs native job execution, writes evidence under `artifacts/eval`, and tears down its temporary Compose project.

```bash
make app-smoke
```

Manual checks against a running `make app-up` stack:

```bash
curl -fsS http://127.0.0.1:18081/api/health
curl -fsS "http://127.0.0.1:18081/api/auth/session?api_key=tryops-viewer-demo-key"
curl -fsS "http://127.0.0.1:18081/api/evaluations/summary?api_key=tryops-viewer-demo-key"
curl -fsS http://127.0.0.1:18081/metrics | head
```

Run one LLM request through the product API:

```bash
curl -fsS http://127.0.0.1:18081/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "tryops-viewer-demo-key",
    "request_id": "readme-llm-001",
    "prompt": "Explain why TryOps uses a native gateway.",
    "model_alias": "champion",
    "max_tokens": 128,
    "structured": true,
    "routing_mode": "direct",
    "user_id": "demo-user",
    "quota_plan": "free"
  }'
```

## Run Lightweight Dev Mode

Use this when you already started the frontend with `npm run dev` and want the backend/database next.

Terminal 1, initialize the zero-config local SQLite database and start FastAPI:

```bash
make db-init
PYTHONPATH=src python -m uvicorn tryops.api:create_app --factory --host 0.0.0.0 --port 8080
```

The SQLite file is created at `artifacts/app/tryops.db`.

Terminal 2, start the React Console with the backend URL:

```bash
VITE_TRYOPS_API_BASE=http://127.0.0.1:8080 npm --prefix web run dev
```

Open `http://127.0.0.1:5173`.

If you already ran `npm --prefix web run dev` without `VITE_TRYOPS_API_BASE`, stop it with `Ctrl-C` and restart it with the command above. The Console needs that env var when FastAPI is running separately on port `8080`.

Quick backend checks:

```bash
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS "http://127.0.0.1:8080/api/auth/session?api_key=tryops-viewer-demo-key"
curl -fsS "http://127.0.0.1:8080/api/dashboard?api_key=tryops-viewer-demo-key"
```

Use the full Postgres-backed local stack instead of SQLite:

```bash
make app-up
```

Then open `http://127.0.0.1:18081`. In this mode the built Console is served by the Rust gateway and the backing services are managed by Docker Compose, so you do not need `npm run dev` unless you are actively editing frontend code.

Build the production UI bundle:

```bash
make web-typecheck web-build
```

Serve the built UI through the native Rust gateway smoke profile:

```bash
make native-static-smoke
```

## Tests And Verification

Core contract tests:

```bash
make test
make native-go-test
make native-rust-test
make native-cpp-test
npm --prefix web run typecheck
```

CI-grade local evidence:

```bash
make native-ci-contract-live
make native-container-contract-sample
make native-dependency-lock-contract-sample
make evaluation-index-sample
```

Full local CI mirror:

```bash
make ci
```

`make ci` is intentionally heavy. It runs Python, Node, Go, Rust, C++, Compose validation, supply-chain evidence, native contracts, and evaluation-index generation.

## Useful Product Samples

LLM:

```bash
make llm-benchmark-sample
make llm-continuous-batching-sample
make llm-fallback-sample
make llm-load-sample
```

VTON:

```bash
make vton-baseline-sample
make vton-preprocess-sample
make vton-job-sample
make vton-advanced-eval-sample
```

Quota, FinOps, and guardrails:

```bash
make quota-sample
make finops-sample
make guardrail-sample
make native-edge-guardrail-smoke
```

Experiments:

```bash
make experiment-routing-sample
make experiment-analysis-sample
```

Promotion, lineage, deployment, and recovery:

```bash
make validate-sample
make pipeline-sample
make deploy-package-sample
make signed-pr-promotion-sample
make registry-webhook-sample
make chaos-sample
```

Observability and governance:

```bash
make dashboard-sample
make alert-sample
make slo-burn-rate-sample
make trace-sample
make governance-sample
```

## Real Model Runs

Most commands work offline through deterministic fallbacks. Use these only when the machine has model dependencies and GPU access:

```bash
python -m pip install -e ".[dev,ml]"
make vton-real-sample
make llm-real-sample
make llm-pareto-sample
make energy-sample
```

Probe an external OpenAI-compatible vLLM server:

```bash
VLLM_BASE_URL=http://127.0.0.1:8000/v1 \
VLLM_MODEL=HuggingFaceTB/SmolLM2-135M-Instruct \
make llm-vllm-probe-sample
```

## Repository Map

```text
web/                       React/Vite/TypeScript Console
src/tryops/                FastAPI BFF, adapters, contracts, fallbacks
native/rust/tryops-gateway Rust Axum gateway and static-serving profile
native/go/                 Go controllers, sidecars, contracts, load tools
native/cpp/                C++ policy/eval/cache/VTON/LLM CLIs
infra/                     Prometheus, Grafana, OTel, Alertmanager, Kubernetes
configs/                   API keys, image contracts, secret and service config
contracts/                 JSON schemas
samples/                   Candidate, eval, and demo payloads
scripts/                   Local automation and evidence generation
tests/                     Python contract tests
artifacts/                 Generated local evidence; ignored by Git
reports/generated/         Generated promotion/model/data cards; ignored by Git
```

## Generated Files

The repo intentionally ignores generated outputs such as:

```text
artifacts/
reports/generated/
web/dist/
web/node_modules/
native/rust/tryops-gateway/target/
.pytest_cache/
.ruff_cache/
__pycache__/
```

If `git status --ignored` shows those paths, that is expected. They are local build/test/evidence outputs and should not be committed.

## Main Docs

- Roadmap: `MLOPS_VTON_LLM_ENTERPRISE_ROADMAP.md`
- Production app plan: `docs/production_app_plan.md`
- API contract: `docs/api_contract.md`
- Enterprise quota: `docs/enterprise_quota.md`
- Serving controls: `docs/serving_controls.md`
- Release engineering: `docs/release_engineering.md`
- Supply chain: `docs/supply_chain.md`
- Observability: `docs/observability_contract.md`
- Demo outline: `docs/presentation_outline.md`
