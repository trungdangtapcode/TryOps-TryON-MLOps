# Roadmap Execution Audit

Date: 2026-06-11

Roadmap source: `MLOPS_VTON_LLM_ENTERPRISE_ROADMAP.md`

## Verified Current State

The repository is no longer only a plan. It now contains:

- Project charter and research summary.
- Open-source enterprise architecture docs.
- Rust gateway product edge: `/api/*` reverse proxy to backend `/v1/*`, request-ID injection, native quota, edge rate/body limits, signed-artifact admin preflight, and container healthcheck mode.
- Rust gateway native Prometheus exporter for request counters, latency histogram buckets, quota decisions, rate-limit rejects, upstream proxy errors, and in-flight proxy requests.
- Go controller scaffold.
- Compiled C++ policy engine.
- Python ML/MLOps scaffold.
- Promotion policy in Python and Rego.
- Dataset validation pipeline.
- VTON metric summary component.
- LLM benchmark summary component.
- Registry metadata helper.
- Generated model card and data card.
- Generated lineage and promotion decision artifacts.
- Sample golden prompts, VTON pairs, and security cases.
- VTON preflight safety and caching layer.
- Deterministic naive VTON baseline with generated PNG output and JSON sidecar.
- Lightweight image metrics: MSE, PSNR, and global luma SSIM approximation.
- VTON comparison artifact and failure-gallery artifact.
- VTON results section.
- Selected SmolLM2-135M-Instruct as the first open-source LLM target.
- Deterministic LLM baseline with structured JSON output, safety flags, quality scoring, latency, memory, and cost metrics.
- LLM benchmark artifact for the golden prompt set.
- LLM prefill/decode phase timing in generation responses, benchmark records, structured logs, and Prometheus metrics.
- OpenTelemetry-compatible API trace spans with W3C-style trace/span IDs, `traceparent` propagation, structured-log correlation, sanitized JSONL span artifacts, and Prometheus trace metrics.
- `/v1` API surface with readiness, structured validation errors, request IDs, safe aliases, canary routing simulation, LLM shadow evaluation, and Prometheus-style metrics.
- C++ native policy CLI integrated with Python promotion evidence.
- C++ native image metrics CLI integrated with VTON comparison artifacts.
- C++ native VTON preprocessing CLI integrated with optional mask and pose artifacts.
- C++ native VTON advanced evaluation CLI integrated with identity embedding proxies, masked garment fidelity, pose consistency, fairness gaps, and Bradley-Terry ranking artifacts.
- Garment-preservation similarity proxy plus verified Transformers CLIP image-image/text scoring in `artifacts/eval/vton_clip/garment_clip_similarity.json`.
- LLM prompt-length and output-length sensitivity benchmark artifact for the local deterministic baseline.
- LLM optimization report with quality-latency-memory Pareto chart generated from the real quantization sweep artifact.
- Usage-based quota enforcement for LLM and VTON requests with hashed user IDs, now backed by the Rust gateway endpoint/CLI for admission evidence.
- Rust gateway services-and-edge wiring: compiled Axum gateway proxies `/api/*` to FastAPI `/v1/*`, adds request IDs, propagates W3C `traceparent`, enforces per-key rate limits, payload limits, and signed-artifact preflight on admin routes; the gateway is now split across 13 focused Rust modules under `native/rust/tryops-gateway/src/`; `Dockerfile.gateway`, `docker-compose.yml`, and `make app-up` wire it as the local product front door.
- Full-stack startup smoke: `native/go/tryops-stack-smoke` is a dependency-free Go checker for the Compose stack; `make app-smoke` now runs in the disposable Compose project `tryops_app_smoke`, recreates smoke volumes before startup, tears them down on exit, and writes `tryops.full_stack_smoke.v1` covering 18/18 checks for Console, SPA fallback, gateway/API, LLM generation, evaluation summary with pipeline-run ledger, VTON comparison, bad-candidate promotion rejection, rollback-state artifact serving, gateway metrics, guardrail, Prometheus, Grafana, MinIO, and MLflow.
- Console Professor Demo mode: `web/src/components/ProfessorDemoView.tsx` renders a seeded seven-step, no-network/no-GPU walkthrough for stack preflight, native quota admission, bad-model blocking, LLM optimization, VTON comparison, promotion lineage, rollback, and governance, with artifact paths visible in the browser.
- Professor demo backup video: `native/go/tryops-demo-recorder` renders the shared Console storyboard into PNG frames and uses FFmpeg to encode `artifacts/demo/professor_demo_video/professor_demo_backup.mp4`; `artifacts/eval/demo_video/professor_demo_video.json` records `tryops.professor_demo_video.v1`, `passed=true`, dimensions, duration, byte size, SHA-256, frame metadata, and the encoder command.
- Native Go VTON/LLM job runner: `native/go/tryops-job-runner` submits direct LLM and async VTON work through the Rust gateway with context deadlines, transient retry backoff, VTON status polling, compact response summaries, and `tryops.native_job_runner.v1` evidence. `make app-smoke` builds and runs it after stack readiness and before refreshing the evaluation index.
- Native Go audit/webhook dispatcher: `native/go/tryops-event-dispatcher` validates promotion, feedback, incident, and quota event envelopes; writes `tryops.native_audit_event.v1` audit JSONL; signs webhook deliveries with HMAC-SHA256; retries transient failures; and writes `tryops.native_event_dispatcher.v1` evidence.
- Pipeline Runs view: `native/go/tryops-evaluation-index` aggregates `run_context.json`, OpenLineage RunEvent, and lineage artifacts into a `pipeline_runs` ledger, `/api/evaluations/summary` serves it, and the React Console renders run/job/model/dataset/trace evidence under the Runs page.
- Live bad-candidate promotion drill: the Console Incident view posts a seeded unsafe VTON candidate to `/api/promotion/evaluate` with Rust gateway signed-artifact preflight, renders the `approved=false` decision and rejection reasons, and the Go full-stack smoke checker verifies `bad_candidate_gate_through_gateway` through the gateway.
- Rollback drill in the Console: deployment rollback JSON artifacts are allowlisted in the API resolver and Rust gateway artifact preflight, the Incident view loads the latest rollback state on demand, and the Go full-stack smoke checker verifies `rollback_state_artifact_through_gateway` through the gateway.
- Native Go gateway benchmark driver: `native/go/tryops-benchmark` starts FastAPI plus the Rust gateway, drives keep-alive load without Python/GIL driver overhead, and writes `tryops.native_gateway_benchmark.v1` for `/health`, direct validated promotion POST, and full edge proxy POST.
- Native Go full-stack load/SLO driver: `native/go/tryops-fullstack-load` starts FastAPI plus the Rust gateway, drives weighted product traffic through `/api/*`, checks per-scenario latency/error/RPS SLOs, records k6/locust availability, and writes `tryops.native_fullstack_load.v1`; the latest local evidence passed 504 requests across six scenarios with zero errors.
- Native Go CI/supply-chain contract: `.github/workflows/ci.yml` defines Python/Node/Go/Rust/C++
  checks, Compose validation, seven Docker Buildx image roles, Syft SPDX SBOM generation, Trivy
  HIGH/CRITICAL scan gating, artifact uploads, and Cosign keyless image signing on non-PR pushes;
  `native/go/tryops-ci-contract` validates the workflow plus `make ci` and writes
  `tryops.native_ci_contract.v1`.
- Native Go SLO regression gate: `native/go/tryops-slo-gate` consumes `tryops.native_gateway_benchmark.v1`, applies latency/error/throughput/ratio rules, exits nonzero on regression, and writes `tryops.native_slo_gate.v1` evidence under `artifacts/eval/slo/`.
- Native Go config contract gate: `native/go/tryops-config-contract` parses `docker-compose.yml` with a real YAML parser, validates enterprise services/envs/Compose secrets/ports/healthchecks/readiness conditions/volumes, checks direct credential-env absence plus `.env.example` coverage, cross-checks gateway env names against Rust source, and writes `tryops.native_config_contract.v1` evidence under `artifacts/eval/config/`.
- Native Go performance budget gate: `native/go/tryops-performance-budget` consumes Rust gateway benchmark output, Go SLO/config-contract reports, C++ perf stats, and native binary artifacts, then writes `tryops.native_performance_budget.v1` plus Markdown for CI job summaries under `artifacts/eval/performance/`.
- Native C++ VTON execution evidence through the API: `src/tryops/vton_native_bridge.py` makes `/v1/vton/infer` expose `tryops.native_vton_execution.v1` with C++ preprocessing and image metrics, persists enriched output sidecars, and stores native quality in request rows for request-detail/dashboard rollups; `make vton-native-api-sample` writes `tryops.vton_native_api.v1` evidence.
- Native quota durability evidence: `TRYOPS_GATEWAY_QUOTA_LEDGER_PATH` makes the Rust gateway and `quota-check` CLI load and atomically replace a local ledger file (`tryops.quota_ledger_file.v1`); `TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN` mirrors accepted usage into a `tryops_quota_usage` upsert ledger; `TRYOPS_GATEWAY_QUOTA_POSTGRES_ADMISSION=true` makes Postgres the authoritative distributed admission ledger using a transaction plus `SELECT ... FOR UPDATE` row locks and fails closed when the Postgres adapter is unavailable; `TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR` mirrors accepted increments to Valkey-compatible `INCRBY`/`EXPIRE` counters; if a non-admission durable mirror cannot initialize, the gateway logs the adapter failure and falls back to the local quota ledger rather than crash-looping; `make native-quota-ledger-smoke` proves usage survives across separate gateway CLI processes and exposes hashed tenant snapshots.
- Native distributed quota admission: `native/go/tryops-distributed-quota` drives concurrent quota requests across two Rust gateway instances backed by the same disposable Postgres ledger. `make native-distributed-quota-smoke` emits `artifacts/eval/quota/native_distributed_quota_admission.json` as `tryops.distributed_quota_admission.v1`; the latest local run allowed exactly 20/32 free-plan LLM requests, rejected 12 globally, recorded zero errors, and passed `no_cluster_quota_oversell`.
- Local secret-loading evidence: `.env.example` documents required local secrets while `.env` remains ignored; Compose now declares four secrets for Postgres, MinIO, MLflow, and the gateway quota DSN; the Rust gateway supports `TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN_FILE`; and the native config contract passes 111 checks over 10 services plus 4 secrets.
- Native Postgres migration/pooling evidence: `infra/postgres/migrations` defines idempotent product/quota DDL; `native/go/tryops-db-migrator` uses pgxpool, records checksums in `tryops_schema_migrations`, emits `tryops.native_postgres_migration.v1`, and live apply against Compose Postgres passed 33/33 checks with pooled ping/acquire plus live table verification.
- Native backup/restore evidence: `native/go/tryops-backup-restore` emits `tryops.native_backup_restore_drill.v1`; plan mode validates Compose storage, restore isolation, required tools, and `infra/backup/restore_drill.cron`; live mode uses container-local PG16 `pg_dump`/`pg_restore` and MinIO `mc mirror`, restoring Postgres into `tryops_restore_drill`, mirroring an object into `tryops-restore-drill`, and passing 50/50 checks with cleanup evidence.
- Native quota read-model and BFF summary: `native/go/tryops-quota-read-model` consumes Rust quota snapshots and emits `tryops.native_quota_read_model.v1` with hashed tenants, limits, utilization, risk, and showback; `/api/quota/summary` serves the contract through scoped admin-read auth; the Console Dashboard renders the read model as tenant risk, used units, showback, and native-source status.
- Product backend BFF routes are live before `create_app()` returns: history, request detail, feedback, dashboard, models, model promotion, and lineage endpoints are registered, scope-gated where required, and covered by isolated SQLite regression tests.
- Native gateway observability: Prometheus scrapes `gateway:8081`, `make native-rust-smoke` verifies `/metrics`, and `tryops-service-overview` carries gateway request-rate, p95-latency, rejection, and upstream-error panels.
- Native OpenTelemetry Collector contract: `infra/otel/collector.yml` defines OTLP gRPC/HTTP, JSONL filelog, resource/batch/memory processors, file exporters, and health checks; Compose runs `otel-collector`; Prometheus scrapes `otel-collector:8888`; the Rust gateway writes native JSONL trace-log envelopes; and `native/go/tryops-observability-contract` emits `tryops.native_observability_contract.v1` with 46/46 checks over Collector, Compose, Prometheus, gateway logs, API spans, API logs, shared trace IDs, service names, model-call metadata, and redaction.
- Native Alertmanager routing contract: `infra/alertmanager/alertmanager.yml` defines page/ticket routing, severity/workload/alertname grouping, inhibition, and a controller webhook receiver; Prometheus forwards alerts to `alertmanager:9093`; Compose runs Alertmanager with healthcheck/storage; the Go controller accepts Alertmanager webhook payloads; and `native/go/tryops-alertmanager-contract` emits `tryops.native_alertmanager_contract.v1` with 24/24 checks over routing, receivers, 16 alert rules, Compose, and Prometheus forwarding.
- Optimized LLM fallback routing from unavailable optimized aliases to the baseline route.
- Timeout handling for synchronous inference requests.
- Local async VTON job submission/status API with queue-depth metrics.
- Least-privilege API-key simulation for promotion and lineage admin actions.
- Endpoint smoke report for readiness, LLM generation, VTON inference, and metrics.
- Structured JSONL API logging with sanitized metadata.
- Latency and quality alert threshold reports with Prometheus alert rules.
- Grafana dashboard provisioning for service health, model quality, and cost/capacity views.
- Local drift reports for VTON image metadata and LLM prompt length/topic distributions.
- NIST AI RMF, OWASP LLM 2025, and responsible-AI residual-risk mapping evidence.
- Native Go LLM guardrail sidecar/CLI with a modular server/CLI/evaluator/metrics layout, PII redaction, injection/output-safety classification, structured-output gating, OWASP LLM 2025 reports, Grafana risk panels, and promotion-gate integration.
- Rust gateway edge guardrail enforcement: `TRYOPS_GATEWAY_GUARDRAIL_URL` makes the compiled gateway call the Go sidecar before proxying `/api/llm/generate`, so prompt-injection/system-prompt leakage can be blocked before Python.
- Native C++ model artifact scanner enforcing SafeTensors-only promotion and rejecting pickle-family model weights through Python, C++, and Rego gates.
- Native C++ model provenance verifier checking local DSSE-shaped signature bundles, in-toto/SLSA predicate type, model artifact digest, payload digest, and signer identity before promotion.
- OpenLineage-standard RunEvent emission beside internal lineage JSON, with native C++ event-envelope validation carried into deployment package evidence.
- Argo CD / Argo Rollouts GitOps manifests for deployment packages, with native C++ validation of Application, Rollout, Service, Kustomization, and canary-step structure.
- FinOps unit economics, hashed-tenant budget showback, budget alert rules, privacy-aware `/v1/llm/generate` semantic caching, native C++ cache lookup, and cache hit/cost/energy savings panels in the cost dashboard.
- Native C++ chaos scenario evaluator covering GPU OOM, slow decode, corrupted weights, and poisoned candidates, with native burn-rate evaluation and automatic rollback record generation.
- Native C++ online experiment router and experiment statistics engine for guarded A/B allocation, holdback, UCB-style bandit traffic shifts, uplift CIs, and sequential early-stop verdicts over the existing routing layer.
- Native C++ VTON advanced evaluator for identity, masked fidelity, pose, fairness, and preference ranking evidence, with generated model-card bias/limitation updates.
- Native C++ LLM batch scheduler comparing request-level static batching with iteration-level continuous batching over a mixed concurrent request stream.
- Dependency lockfile evidence: `uv.lock` pins the Python project resolution, including
  `accelerate` and `bitsandbytes`; `web/package-lock.json`, Rust `Cargo.lock`, and Go `go.sum`
  cover the native/frontend surfaces; the native Go contract verifies all four ecosystems.
  The older generated `requirements.lock` remains as a local SPDX fallback input.
- Kubeflow-target orchestration skeleton with a validated seven-step enterprise DAG.
- Deployment package, release notes, rollback plan, rollback record, run context, experiment log, and LLM load-test artifacts.
- **R1 real LLM (GPU): real `SmolLM2-135M-Instruct` inference via Transformers on CUDA (NVIDIA L4), behind the unchanged `tryops.llm_generation.v1` / `tryops.llm_benchmark.v1` contracts, with a per-record deterministic fallback. Measured ~18.5 tok/s and 0.28 GB VRAM on the golden prompt set (`make llm-real-sample`).**
- **Native C++ benchmark statistics + SLO engine (`tryops_perf_stats`): latency percentiles (p50/p95/p99), throughput aggregation, and pass/fail SLO gating run in compiled C++ instead of Python, with a Python marshaling bridge and graceful degradation when the binary is absent (`make native-perf-stats-sample`). Demonstrated adapter-specific SLO calibration: the real GPU model fails a baseline-calibrated 100 ms p95 gate and passes a GPU-calibrated gate.**
- **Native C++ SLO burn-rate engine (`tryops_burn_rate`): formal LLM, VTON, and control-plane SLO error budgets plus Google-SRE-style multi-window burn-rate alerts run in compiled C++ with Python marshaling (`make slo-burn-rate-sample`). Current local evidence is clean; the regression drill returns a page verdict.**
- **Native Go LLM guardrail sidecar (`tryops-guardrail`): `/v1/llm/generate` can call a separate Go HTTP sidecar before routing/quota/generation, and the Rust gateway can call the same sidecar before proxying `/api/llm/generate`. The service is split into server, CLI, evaluator, metrics, and contract modules. It blocks prompt injection, system-prompt leakage, secret disclosure, unbounded consumption, unsafe agency, and output leaks; it emits `tryops.native_guardrail.v1`, `tryops.guardrail_report.v1`, native Prometheus metrics, gateway edge-decision metrics, and promotion-gate metadata (`make guardrail-sample`, `make native-guardrail-smoke`, `make native-edge-guardrail-smoke`).**
- **Native Rust auth preflight (`tryops-gateway`): protected `/api/*` routes are now checked at the edge before FastAPI. The gateway loads the local hashed API-key registry, verifies scoped API keys from query/header/body, supports optional HS256 bearer JWTs with `TRYOPS_GATEWAY_JWT_HS256_SECRET`, forwards non-secret principal metadata, and exports `tryops_gateway_auth_decisions_total`. `make app-smoke` proves missing-key 401 and missing-scope 403 responses from the gateway.**
- **Native Rust semantic-cache admission plus C++ edge lookup (`tryops-gateway`): `native/rust/tryops-gateway/src/semantic_cache.rs` evaluates LLM cache admission before proxying to FastAPI, skips disabled/invalid/sensitive prompts, hashes admitted cache keys, optionally invokes `artifacts/native/tryops_semantic_cache_cli` for C++ vector lookup, forwards bounded `x-tryops-edge-cache-*` metadata, and exports `tryops_gateway_semantic_cache_admissions_total` plus `tryops_gateway_semantic_cache_lookups_total`; `make native-edge-cache-smoke` proves admitted, sensitive-skip, and native C++ hit decisions without Python.**
- **Native Go job runner (`tryops-job-runner`): VTON/LLM background-style execution now has a compiled runner split across config, payload, HTTP, retry, runner, response-summary, report, asset, and test modules. It uses Go `context` deadlines, retries transient submission failures, polls async VTON jobs, and emits `artifacts/eval/jobs/native_job_runner_report.json` (`tryops.native_job_runner.v1`). `make native-job-runner-test`, `make native-job-runner-sample`, and `make app-smoke` passed.**
- **Native Go SLO regression gate (`tryops-slo-gate`): CI-style benchmark gating now runs in compiled Go. The module is split across config, load, policy, evaluation, report, and test files; it consumes `artifacts/eval/gateway_benchmark/native_gateway_benchmark.json`, fails on error/latency/throughput/overhead regressions, and emits `artifacts/eval/slo/native_slo_gate_report.json` (`tryops.native_slo_gate.v1`). `make native-slo-gate-test`, `make native-slo-gate-sample`, and `make evaluation-index-sample` passed.**
- **Native Go event dispatcher (`tryops-event-dispatcher`): audit/webhook fanout now runs in compiled Go for promotion, feedback, incident, and quota events. The module is split across config, event loading/validation, audit sink, HMAC signature, webhook delivery, sample receiver, report, and tests. `make native-event-dispatcher-sample` writes `artifacts/eval/events/native_event_dispatcher_report.json` plus `artifacts/eval/events/native_audit_events.jsonl`, proving four audit writes and four signed webhook deliveries.**
- **Native Go DVC/MinIO verifier (`tryops-data-versioning`): `make dvc-minio-sample` runs DVC repro/push and a dependency-free Go S3 verifier that signs ListObjectsV2 requests to MinIO, proving 12 local DVC cache objects are present remotely in `s3://tryops-artifacts/dvc`.**
- **Native C++ model artifact scanner (`tryops_model_scan`): SafeTensors-only promotion is enforced before model shipping. The scanner validates `.safetensors` headers, rejects pickle-family `.bin`/`.pt`/`.pkl` artifacts without deserialization, and feeds Python, C++, and Rego promotion gates (`make model-supply-chain-sample`).**
- **Native C++ model provenance verifier (`tryops_model_provenance`): model weights are bound to a local DSSE-shaped signature bundle and in-toto/SLSA provenance statement. The native verifier checks artifact digest, payload digest, signer identity, and `https://slsa.dev/provenance/v1` before Python/C++/Rego promotion gates accept a candidate (`make model-supply-chain-sample`).**
- **Native C++ OpenLineage validator (`tryops_openlineage`): promotion runs now emit `openlineage_run_event.json` beside the internal `lineage.json`. The native validator checks OpenLineage run state, event time, UUID-shaped run ID, job identity, producer/schema URL, and input/output dataset sections before deployment evidence is packaged (`make pipeline-sample`).**
- **Native C++ GitOps validator (`tryops_gitops`): deployment packages now include an Argo CD Application, Argo Rollouts canary Rollout, stable/canary Services, and Kustomization. The native validator checks GitOps manifest structure, candidate labels, and canary `setWeight`/`pause` steps before the package is marked deployable (`make deploy-package-sample`).**
- **Native Go signed promotion PR trigger: the controller now accepts GitHub-style signed `pull_request.closed` webhooks, validates `X-Hub-Signature-256`, requires a merged PR to `main`/`production`, code-owner approval, verified commit, status checks, model provenance, native policy, OpenLineage, and GitOps evidence, then returns promotion plus registry-alias sync actions (`make signed-pr-promotion-sample`).**
- **Native Go registry-webhook deploy trigger: the controller now accepts signed MLflow-style `model_version_alias.created` webhooks, validates HMAC signature and freshness headers, checks promotion/OpenLineage/GitOps evidence in the deployment package payload, re-runs the native C++ `tryops_policy_cli` over the full webhook `policy_candidate` when `TRYOPS_CONTROLLER_POLICY_CLI` is configured, and only then returns GitOps sync plus Argo Rollouts canary actions (`make registry-webhook-sample`).**
- **Native C++ online experiment router/statistics (`tryops_experiment_router`, `tryops_experiment_stats`): A/B allocation, holdback, guardrail eligibility, UCB-style bandit scoring, Agresti-Caffo uplift CIs, and Wald-style sequential early stopping now run in compiled C++ with Python marshaling bridges. `make experiment-routing-sample` proves the unsafe candidate is blocked and the bandit route shifts/serves traffic to the stronger challenger; `make experiment-analysis-sample` proves holdback uplift CI and early-stop evidence, while reusing native `tryops_eval_stats` for a Theme-N bootstrap delta CI.**
- **Native C++ VTON advanced evaluator (`tryops_vton_eval`): identity-preservation embedding-proxy distance, garment-region masked fidelity, pose-consistency scoring, skin-tone/body-type fairness gaps, and Bradley-Terry preference strengths now run in compiled C++ with Python marshaling (`make vton-advanced-eval-sample`). The report updates the generated model card with advanced-evaluation, bias, and limitation notes.**
- **Native C++ continuous-batching scheduler (`tryops_batch_scheduler`): request-level static batching and iteration-level continuous batching are compared in compiled C++ with Python marshaling (`make llm-continuous-batching-sample`). Current local evidence uses a 20-request mixed prompt/decode workload and records 1.218x modeled throughput, 19.1% lower p95 latency, and decode-slot utilization 0.623 -> 1.0 for continuous batching. This proves scheduler behavior, not live vLLM serving.**
- **R2 quantization Pareto (GPU): real fp16/8-bit/4-bit sweep of `Qwen2.5-0.5B-Instruct` on CUDA via bitsandbytes, each variant SLO-gated by the native C++ engine, with non-dominated Pareto frontier + auto-recommendation (`make llm-pareto-sample`). Measured: fp16 1.01 GB / 21.8 tok/s, 8-bit 0.65 GB / 4.5 tok/s (dominated, SLO-fail), 4-bit NF4 0.48 GB / 11.3 tok/s (SLO-pass, recommended — 2.1x VRAM reduction). Pure-Python frontier math is unit-tested without a GPU; the sweep degrades to the deterministic baseline when torch/bitsandbytes are absent.**
- **Theme M Green MLOps (GPU): real NVML GPU power sampling around inference (`src/tryops/energy.py`), native C++ `tryops_energy_stats` engine for energy/CO2e/SCI/EDP aggregation, and a carbon-aware promotion gate. Smoke-safe demo (`make energy-demo-sample`, in `make smoke`) plus the real per-variant sweep (`make energy-sample`). Measured on the L4: fp16 0.52 Wh/1k tokens (greenest); 8-bit 1.78 (3.4x) and 4-bit 0.81 (1.55x) — a real finding that quantization's VRAM win costs energy because slower decode keeps the GPU busy longer. Deterministic power-trace fallback keeps the pipeline offline-reproducible.**
- **Energy/CO2e Grafana visibility: `tryops-cost-capacity` now includes Energy per 1k Tokens, CO2e per 1k Tokens, and Cost vs Energy Correlation panels, and `make dashboard-sample` requires those panels. Local evidence comes from `artifacts/eval/energy/energy_sweep.json`; production exporters should emit `tryops_energy_wh_per_1k_tokens`, `tryops_co2e_g_per_1k_tokens`, and `tryops_request_cost_usd_per_1k_tokens`.**
- **Console optimization/Pareto/sustainability panel: native Go `tryops-evaluation-index` joins the Pareto, leaderboard, and energy artifacts into `optimization_panel`; `/api/evaluations/summary` serves it through the Rust gateway; the React Evaluation view renders recommendation, judge backend, interactive quality-vs-latency frontier, per-variant VRAM/energy/SCI, and carbon-gate verdict; `make app-smoke` requires `optimization_panel`, `recommended_variant="4bit"`, and `carbon_gate_verdict="pass"`.**
- **Real diffusion VTON (GPU): SD1.5 inpainting refines a garment composited onto the person torso, behind the unchanged `tryops.vton_baseline.v1` contract with a deterministic fallback (`make vton-real-sample`). Measured on the L4: 3.3 s latency, 2.8 GB VRAM; native C++ image metrics on the real output (PSNR 16.8, SSIM 0.54). Energy sampling degraded to the deterministic trace under GPU load (honest fallback).**
- Tests and `make smoke`.

## Evidence Files

- `README.md`
- `docs/project_charter.md`
- `docs/literature_review.md`
- `docs/architecture.md`
- `docs/service_level_objectives.md`
- `docs/dashboard_design.md`
- `docs/rollback_fallback.md`
- `docs/architecture_review.md`
- `docs/adr/`
- `src/tryops/`
- `native/`
- `native/go/tryops-guardrail/`
- `Dockerfile.guardrail`
- `contracts/`
- `samples/`
- `tests/`
- `src/tryops/pipelines/vton_preflight.py`
- `src/tryops/pipelines/llm_baseline.py`
- `src/tryops/pipelines/llm_benchmark.py`
- `src/tryops/pipelines/llm_phase_timing.py`
- `src/tryops/guardrails.py`
- `src/tryops/api_contracts.py`
- `src/tryops/routing.py`
- `src/tryops/observability.py`
- `src/tryops/tracing.py`
- `src/tryops/endpoint_smoke.py`
- `src/tryops/quota.py`
- `src/tryops/timeouts.py`
- `src/tryops/jobs.py`
- `src/tryops/alerts.py`
- `src/tryops/dashboards.py`
- `src/tryops/drift.py`
- `src/tryops/governance.py`
- `src/tryops/auth.py`
- `src/tryops/supply_chain.py`
- `src/tryops/orchestration.py`
- `src/tryops/native_policy.py`
- `src/tryops/native_image_metrics.py`
- `src/tryops/native_vton_preprocess.py`
- `src/tryops/native_burn_rate.py`
- `src/tryops/native_model_scan.py`
- `src/tryops/native_openlineage.py`
- `src/tryops/gitops.py`
- `src/tryops/native_gitops.py`
- `src/tryops/native_experiment_router.py`
- `src/tryops/native_experiment_stats.py`
- `src/tryops/semantic_cache.py`
- `src/tryops/finops.py`
- `src/tryops/native_chaos.py`
- `src/tryops/chaos.py`
- `src/tryops/slo.py`
- `src/tryops/pipelines/garment_similarity.py`
- `src/tryops/pipelines/llm_sensitivity.py`
- `src/tryops/pipelines/llm_optimization_report.py`
- `src/tryops/pipelines/vton_preprocessing.py`
- `src/tryops/deployment.py`
- `src/tryops/run_context.py`
- `src/tryops/load_test.py`
- `native/cpp/tryops_policy/src/tryops_policy_cli.cpp`
- `native/cpp/tryops_image_metrics/src/tryops_image_metrics_cli.cpp`
- `native/cpp/tryops_vton_preprocess/src/tryops_vton_preprocess_cli.cpp`
- `native/cpp/tryops_burn_rate/src/tryops_burn_rate_cli.cpp`
- `native/cpp/tryops_model_scan/src/tryops_model_scan_cli.cpp`
- `native/cpp/tryops_openlineage/src/tryops_openlineage_cli.cpp`
- `native/cpp/tryops_gitops/src/tryops_gitops_cli.cpp`
- `native/cpp/tryops_experiment_router/src/tryops_experiment_router_cli.cpp`
- `native/cpp/tryops_experiment_stats/src/tryops_experiment_stats_cli.cpp`
- `native/go/tryops-controller/*.go` (modular controller server, handlers, signatures, promotion logic, helpers, and contracts)
- `scripts/simulate_signed_pr_promotion.py`
- `scripts/simulate_registry_webhook.py`
- `scripts/evaluate_online_experimentation.py`
- `scripts/evaluate_online_experiment_analysis.py`
- `src/tryops/native_quota.py`
- `src/tryops/quota_read_model.py`
- `native/cpp/tryops_vton_eval/src/tryops_vton_eval_cli.cpp`
- `src/tryops/vton_native_bridge.py`
- `src/tryops/native_vton_eval.py`
- `scripts/evaluate_vton_advanced.py`
- `samples/eval/vton_preference_study.json`
- `native/cpp/tryops_chaos/src/tryops_chaos_cli.cpp`
- `native/cpp/tryops_semantic_cache/include/tryops_semantic_cache.hpp`
- `native/cpp/tryops_semantic_cache/src/tryops_semantic_cache.cpp`
- `native/cpp/tryops_semantic_cache/src/tryops_semantic_cache_cli.cpp`
- `native/cpp/tryops_semantic_cache/tests/test_semantic_cache.cpp`
- `native/rust/tryops-gateway/src/*.rs` (13-file modular Rust gateway)
- `native/go/tryops-stack-smoke/*.go` (full-stack readiness, artifact, evaluation, and bad-candidate gate probes)
- `native/go/tryops-fullstack-load/*.go` (native full-stack gateway/BFF load and SLO evidence)
- `native/go/tryops-ci-contract/*.go` (native GitHub Actions, SBOM, scan, signing, and `make ci` contract gate)
- `native/go/tryops-job-runner/*.go` (native LLM/VTON job runner with deadline, retry, and polling coverage)
- `native/go/tryops-slo-gate/*.go` (native benchmark SLO regression gate)
- `native/go/tryops-performance-budget/*.go` (native Rust/Go/C++ performance budget gate)
- `native/go/tryops-event-dispatcher/*.go` (native audit/webhook event dispatcher)
- `native/go/tryops-evaluation-index/*.go` (evaluation report and pipeline-run ledger indexing)
- `native/go/tryops-quota-read-model/*.go` (native quota read model and showback report)
- `native/go/tryops-runtime-telemetry/*.go` (native LLM/GPU runtime telemetry exporter)
- `native/go/tryops-observability-contract/*.go` (native OpenTelemetry Collector and trace/log correlation gate)
- `native/go/tryops-alertmanager-contract/*.go` (native Alertmanager routing and Prometheus alerting gate)
- `infra/otel/collector.yml`
- `infra/alertmanager/alertmanager.yml`
- `artifacts/eval/runtime/native_runtime_telemetry.json`
- `artifacts/eval/runtime/native_runtime_telemetry.prom`
- `artifacts/eval/ci/native_ci_contract.json`
- `artifacts/eval/observability/native_observability_contract.json`
- `artifacts/eval/alerts/native_alertmanager_contract.json`
- `artifacts/eval/load/native_fullstack_load.json`
- `artifacts/logs/gateway_events.jsonl`
- `web/src/components/PipelineRunsView.tsx`
- `web/src/components/IncidentView.tsx`
- `web/src/components/DashboardView.tsx`
- `web/src/api.ts`
- `web/src/data.ts`
- `web/src/types.ts`
- `web/src/styles.css`
- `Dockerfile.gateway`
- `docker-compose.yml`
- `Makefile`
- `docs/api_contract.md`
- `docs/llm_guardrails.md`
- `docs/model_supply_chain.md`
- `docs/finops_semantic_cache.md`
- `docs/chaos_reliability.md`
- `docs/observability_contract.md`
- `docs/opentelemetry_tracing.md`
- `docs/drift_monitoring.md`
- `docs/enterprise_quota.md`
- `docs/admin_auth.md`
- `docs/serving_controls.md`
- `docs/release_engineering.md`
- `docs/reproducibility_checklist.md`
- `docs/experiment_log.md`
- `docs/native_image_metrics.md`
- `docs/vton_preprocessing.md`
- `docs/garment_similarity.md`
- `docs/llm_sensitivity.md`
- `docs/llm_phase_timing.md`
- `docs/responsible_ai_risk_mapping.md`
- `docs/supply_chain.md`
- `docs/orchestration.md`
- `configs/governance_risk_controls.json`
- `configs/api_keys.json`
- `infra/grafana/dashboards/tryops-guardrails.json`
- `infra/prometheus/tryops_finops_alerts.yml`
- `artifacts/eval/guardrails/guardrail_report.json`
- `artifacts/eval/model_supply_chain/model_supply_chain_report.json`
- `artifacts/eval/model_supply_chain/safe_model_artifact_scan.json`
- `artifacts/eval/model_supply_chain/unsafe_model_artifact_scan.json`
- `reports/generated/vton-catvton-2026-06-11-001/openlineage_run_event.json`
- `reports/generated/vton-catvton-2026-06-11-001/openlineage_validation.json`
- `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/application.yaml`
- `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/rollout.yaml`
- `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/services.yaml`
- `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/gitops_validation.json`
- `artifacts/eval/signed_pr/signed_pr_promotion_report.json`
- `artifacts/eval/registry_webhook/registry_webhook_report.json`
- `artifacts/eval/experiments/online_experiment_report.json`
- `artifacts/eval/experiments/online_experiment_analysis_report.json`
- `artifacts/eval/finops/finops_report.json`
- `artifacts/eval/finops/unit_economics.json`
- `artifacts/eval/finops/budget_showback.json`
- `artifacts/eval/finops/semantic_cache_report.json`
- `artifacts/eval/chaos/chaos_drill_report.json`
- `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/auto_rollback_record.json`
- `configs/model_sources.json`
- `configs/dataset_licenses.json`
- `configs/service_level_objectives.json`
- `uv.lock`
- `requirements.lock`
- `artifacts/eval/dependencies/native_dependency_lock_contract.json`
- `scripts/generate_orchestration_skeleton.py`
- `scripts/generate_llm_optimization_report.py`
- `scripts/validate_dataset_manifest.py`
- `pipelines/kubeflow/tryops_pipeline.py`
- `artifacts/eval/quota/quota_usage.json`
- `artifacts/eval/auth/api_key_auth_report.json`
- `artifacts/eval/supply_chain/dependency_lock.json`
- `artifacts/eval/supply_chain/sbom.spdx.json`
- `artifacts/eval/supply_chain/supply_chain_report.json`
- `artifacts/eval/orchestration/tryops_pipeline_dag.json`
- `artifacts/eval/orchestration/tryops_pipeline.kfp.yaml`
- `artifacts/eval/orchestration/orchestration_report.json`
- `artifacts/eval/llm_pareto/pareto.json`
- `artifacts/eval/llm_optimization_report/llm_optimization_report.md`
- `artifacts/eval/llm_optimization_report/llm_pareto_chart.svg`
- `artifacts/eval/llm_optimization_report/llm_pareto_metrics.csv`
- `artifacts/eval/llm_optimization_report/llm_optimization_report.json`
- `artifacts/eval/llm_fallback/fallback.json`
- `artifacts/eval/vton_jobs/job.json`
- `artifacts/eval/endpoint_smoke/deployed_endpoint_smoke.json`
- `artifacts/eval/endpoint_smoke/vton_output.png`
- `artifacts/eval/governance/governance_report.json`
- `artifacts/eval/alerts/alert_report.json`
- `artifacts/eval/dashboards/dashboard_report.json`
- `artifacts/eval/drift/image_metadata_drift.json`
- `artifacts/eval/drift/prompt_topic_drift.json`
- `artifacts/eval/drift/drift_summary.json`
- `artifacts/eval/traces/trace_sample.json`
- `artifacts/eval/traces/api_spans.jsonl`
- `artifacts/eval/traces/api_events.jsonl`
- `artifacts/eval/slo/slo_burn_rate_report.json`
- `artifacts/logs/api_events.jsonl`
- `artifacts/eval/llm_baseline/benchmark.json`
- `infra/prometheus/tryops_alerts.yml`
- `infra/prometheus/tryops_burn_rate_alerts.yml`
- `infra/grafana/provisioning/dashboards/tryops.yml`
- `infra/grafana/dashboards/tryops-service-overview.json`
- `infra/grafana/dashboards/tryops-model-quality.json`
- `infra/grafana/dashboards/tryops-cost-capacity.json`
- `reports/generated/vton-catvton-2026-06-11-001/`

## Verified Commands

```bash
make smoke
make experiment-routing-sample
make experiment-analysis-sample
make vton-advanced-eval-sample
make llm-continuous-batching-sample
make dashboard-sample
make llm-optimization-report-sample
make trace-sample
make slo-burn-rate-sample
make guardrail-sample
make model-supply-chain-sample
make finops-sample
make chaos-sample
make native-go-test
make native-go-smoke
make native-rust-test
make native-rust-smoke
make gateway-benchmark
make gateway-benchmark-native
docker compose config
```

This verifies:

- Python unit tests.
- Passing candidate promotion gate.
- Local promotion pipeline artifact generation.
- Synthetic VTON baseline and comparison artifact generation.
- Local LLM golden-prompt benchmark artifact generation.
- LLM prefill/decode phase timing in benchmark artifacts and Prometheus-compatible metrics.
- OpenTelemetry-compatible trace/span context, sanitized local span artifacts, structured-log trace correlation, and trace Prometheus metrics.
- Shared native trace/log envelope contract across Rust, Go, C++, and FastAPI, validated by `make native-trace-envelope-sample` into `tryops.native_trace_envelope.v1`.
- Split container image contract for gateway, controller, guardrail, benchmark, C++ tools, API, and web assets, validated by `make native-container-contract-sample` into `tryops.native_container_contract.v1`; the current contract passes 89/89 checks and includes Rust builder/runtime ABI-suite compatibility for Rust-containing images.
- Formal workload SLO error budgets and native C++ multi-window burn-rate evaluation.
- API contract, routing, validation, and observability unit tests.
- Native C++ policy CLI bridge comparison.
- Native C++ image metrics bridge comparison.
- Native C++ VTON preprocessing bridge comparison.
- Garment-preservation similarity proxy and OpenCLIP dependency readiness reporting.
- LLM prompt/output length sensitivity benchmark artifact.
- LLM quantization Pareto report and chart generation.
- Usage-based quota simulation artifact.
- Least-privilege API-key authorization simulation artifact.
- Native dependency-lock contract, SPDX SBOM fallback, and source/license inventory evidence.
- Kubeflow-target orchestration skeleton and DAG validation evidence.
- Optimized LLM fallback routing artifact.
- Async VTON job simulation artifact.
- Endpoint smoke report for VTON and LLM `/v1` inference paths.
- Governance risk report covering NIST AI RMF functions, OWASP LLM 2025 risks, and residual responsible-AI limitations.
- Native Go LLM guardrail sidecar/CLI tests, sidecar smoke, OWASP risk report, and Grafana guardrail dashboard validation.
- Native Go controller unit tests, build, and promotion-reconcile smoke with HTTP 202/422 evidence.
- Modular Rust gateway binary artifact smoke/benchmark evidence against Python FastAPI.
- Rust gateway `/api/*` proxy, signed-admin preflight, rate/payload limits, healthcheck mode, and compose syntax validation.
- Rust gateway HTTPS termination through axum-server/rustls plus optional Compose `gateway-tls` profile, validated by `make native-tls-contract-sample` and live `make native-tls-smoke` into `tryops.native_tls_contract.v1`.
- Native Rust gateway Prometheus metrics and Grafana service-overview panels.
- Rust gateway edge guardrail smoke proving LLM01/LLM07 prompts are rejected before the Python backend.
- FastAPI product backend route-registration and auth-gating regression evidence for the P2 product BFF.
- Native C++ model artifact scan gate, safe/unsafe artifact scans, and Python/native promotion-gate rejection demo.
- Native C++ model provenance verification, local DSSE-shaped signature bundle, in-toto/SLSA statement, and Python/native/Rego promotion-gate provenance requirement.
- Native C++ semantic-cache lookup, unit economics, budget showback, and cache savings evidence.
- Native C++ chaos scenario evaluation, native burn-rate page verdicts for injected faults, and auto-rollback artifact generation.
- Timeout and async job route tests.
- Structured JSONL log tests and local log artifact.
- Alert threshold report and Prometheus alert-rule artifact.
- Grafana dashboard provisioning and dashboard JSON validation.
- Local VTON image metadata and LLM prompt/topic drift report generation.
- Deployment package and rollback artifact generation.
- Native C++ policy engine compilation and execution.
- LLM optimization Markdown, CSV, SVG Pareto chart, and audit JSON from the measured Pareto artifact.
- Native Go professor demo acceptance: `make professor-demo-acceptance` runs the bad-candidate gate
  live and validates the seeded Pareto, energy, full-stack, native quota, VTON, lineage, promotion,
  rollback, governance, Console demo view, and seeded demo data contract into
  `artifacts/eval/demo_acceptance/professor_demo_acceptance.json`.
- Native Go professor demo video: `make professor-demo-video` writes
  `artifacts/eval/demo_video/professor_demo_video.json` and
  `artifacts/demo/professor_demo_video/professor_demo_backup.mp4`, giving the project a deterministic
  offline MP4 backup for the professor walkthrough.
- Native Go vulnerability scan runner: `make vulnerability-scan-sample` runs available local scanner
  coverage (`npm audit` for `web/` here), writes `tryops.vulnerability_scan.v1`, and records missing
  production scanners instead of treating absent Trivy/Syft/Grype/pip-audit/Cosign coverage as a pass.
- Native Go evaluation index and Console viewer: `make evaluation-index-sample` writes
  `artifacts/eval/evaluation_index/evaluation_index.json` as `tryops.evaluation_index.v1`; the API
  serves it through `/api/evaluations/summary`; the React Console has an Evaluation view; and
  `make app-smoke` verifies that endpoint through the Rust gateway.
- Native Go full-stack load SLO evidence: `make native-fullstack-load-sample` writes
  `artifacts/eval/load/native_fullstack_load.json` as `tryops.native_fullstack_load.v1`, covering
  health, RBAC session, evaluation summary, quota summary, LLM generation, and operator promotion
  gate traffic through the Rust gateway. The latest local run passed 6/6 scenarios with 504 total
  requests, zero errors, worst p95 39.965 ms, and explicit `k6`/`locust` unavailability records.
- Native Go CI supply-chain contract evidence: `make native-ci-contract-live` writes
  `artifacts/eval/ci/live_supply_chain_report.json` as `tryops.live_supply_chain.v1` and
  `artifacts/eval/ci/native_ci_contract.json` as `tryops.native_ci_contract.v1`, proving 17/17
  checks across GitHub Actions OIDC/artifact permissions, language tests, Compose validation,
  seven-image Docker Buildx matrix, Syft SPDX SBOM generation, Trivy HIGH/CRITICAL scan gating,
  Cosign keyless signing, local live Syft/Trivy/Cosign execution, `make ci`, and referenced
  supply-chain/vulnerability/container reports.
- Native Go dependency-lock contract evidence: `make native-dependency-lock-contract-sample`
  writes `artifacts/eval/dependencies/native_dependency_lock_contract.json` as
  `tryops.native_dependency_lock_contract.v1`, proving 89/89 checks across `uv.lock`,
  `web/package-lock.json`, Rust `Cargo.lock`, and Go module checksum coverage. Current evidence
  records 326 locked Python packages, 59 Node packages, 228 Rust crates, and 32 Go modules.
- Native Go secret-rotation/workload-identity contract evidence: `make native-secret-rotation-contract-sample`
  writes `artifacts/eval/secrets/native_secret_rotation_contract.json` as
  `tryops.native_secret_rotation_contract.v1`, proving 50/50 plan checks across Vault KV policy,
  hash-only API-key registry rotation, `.env.example` live identity knobs, Compose secret mounts,
  Kubernetes Vault `SecretStore`, `ExternalSecret` coverage for 8 managed secrets, a
  non-automounted runtime ServiceAccount, and a projected service-account token for Vault auth.
  `make native-secret-rotation-live` now runs a disposable Vault 1.19 dev server and upgrades the
  same report to `coverage_level=native_secret_rotation_live_vault_kv_rotation` with 65/65 checks,
  5 live KV paths, 8 rotated managed-secret properties, token-file auth, and KV versioning 1..2.
- Native Go optimization index and Console panel: `artifacts/eval/evaluation_index/evaluation_index.json`
  contains `optimization_panel` with the recommended LLM variant, leaderboard rank, Pareto-frontier
  state, per-variant VRAM/energy/SCI, and carbon-gate verdict; the React Evaluation view renders the
  interactive panel; and `make app-smoke` verifies the payload through the Rust gateway.
- Production online experimentation surface: FastAPI accepts `experiment_ab` and `experiment_bandit`
  on `/api/llm/generate`, exposes `/api/experiments/route`, `/api/experiments/analyze`, and
  `/api/experiments/summary`, and delegates guarded A/B plus UCB bandit routing to the native C++
  `tryops_experiment_router` when present. The React Console now includes an Experiments board and
  the LLM Playground can exercise the production experiment path; focused API tests verify RBAC,
  guarded candidate blocking, and LLM generation through `experiment_bandit`.
- Rust gateway auth preflight: `native/rust/tryops-gateway/src/auth.rs` validates scoped API keys and
  optional HS256 JWTs before proxying protected routes to FastAPI; Docker builds the gateway image
  with `configs/api_keys.json`; and `artifacts/eval/full_stack/full_stack_smoke.json` proves
  missing-key 401, missing-scope 403, and `tryops_gateway_auth_decisions_total` metrics.
- RBAC session and role-aware Console nav: `configs/api_keys.json` defines viewer/operator/admin
  principals, FastAPI returns `tryops.rbac_session.v1`, the Rust gateway requires `session:read` for
  `/v1/auth/session`, and the React shell hides views outside the active permission set.
- VTON comparison artifact serving and Console gallery: `/api/vton/comparison` serves
  `tryops.vton_comparison.v1` with artifact URLs, `/api/artifacts/file` serves allowlisted PNG/JSON
  artifacts behind API-key auth, the Rust gateway preflights artifact paths before proxying, the
  Console renders person/garment plus side-by-side output cards, and `make app-smoke` verifies both
  comparison JSON and PNG image serving through the gateway.

## Important Incomplete Work

These remain intentionally unchecked because evidence is not strong enough yet:

- Real VTON model integration.
- Neural VTON masks and pose extraction with SAM, SCHP, DensePose, or OpenPose.
- Fixed-set CLIP/OpenCLIP garment similarity with confidence intervals. The seeded sample now has verified Transformers CLIP execution, but the production claim still needs a benchmark sweep and pinned local checkpoints.
- Representative VTON identity/fairness evaluation. The native advanced evaluator and seeded preference/fairness fixture exist, but production claims still require a consent-aware neural face-embedding model and representative human evaluation panel.
- live AWQ / GPTQ loading, live llama.cpp generation, live vLLM variants, and a larger base model. Real FP16 plus bitsandbytes 8-bit/4-bit Pareto is now done (R1/R2 above), native C++ GGUF preflight now validates a real SmolLM2 Q2_K artifact, native Go now verifies suitable Qwen GPTQ/AWQ candidates plus missing loader runtimes, and native Go provides the vLLM serving probe harness. AWQ or a larger model is needed to reach the 3.5x headline, GPTQModel/AutoGPTQ and AWQ/AutoAWQ are needed for live quantized loading, llama.cpp CLI is needed for live GGUF generation, and a running vLLM endpoint is needed for the continuous-batching throughput curve.
- Live MLflow server writes.
- Full live Prometheus/Grafana dashboard coverage from production traffic. The service dashboard is wired to local API metrics, but quality and cost dashboards still need production metric exporters.
- Production drift windows from sanitized live traffic. The local drift report contract exists, but the current sample uses deterministic simulated current windows.
- Billing-ledger validation beyond quota admission. The Rust gateway now owns quota admission, optional local file durability, Postgres distributed admission, Postgres usage upsert mirroring, Valkey-compatible counter mirroring, and hashed tenant snapshots; full billing-plan/invoicing validation remains future product work.
- Production identity provider integration. The local API-key registry plus Rust edge preflight proves least-privilege scopes and an optional local HS256 JWT path, but production should use OIDC/JWKS, workload identity, or Keycloak-backed gateway validation.
- Durable server-side async queue. The native Go job runner now proves deadline-bound client execution and polling, but the API-side VTON queue is still in-memory and is not a production queue.
- External Alertmanager notification routing. Local Prometheus rules, Alertmanager page/ticket routing,
  inhibition, and the Go controller webhook are wired and validated; real pager/chat/ticket
  credentials still need live vault/workload-identity rotation under PA060.
- Production Kubernetes External Secrets sync. PA060 now has live local Vault KV write/read/rotation
  evidence with token-file auth, but a real cluster should still exercise the External Secrets
  controller and Vault Kubernetes auth TokenReview flow.
- KServe/Kubeflow live deployment. The local Kubeflow-target orchestration skeleton exists, but there is no cluster execution or pipeline upload yet.
- Live Syft/Trivy/Cosign execution in this workspace is now covered by `make native-ci-contract-live`.
  The latest local evidence emits `tryops.live_supply_chain.v1` with 613 Syft packages, 0
  HIGH/CRITICAL Trivy findings, a verified Cosign SBOM signature, and
  `tryops.native_ci_contract.v1` with `production_ready=true`. Optional secondary scanners
  (Grype, pip-audit, gitleaks, osv-scanner) are still recorded as fallback coverage gaps.
- Real Sigstore keyless OIDC and Rekor transparency-log verification. Local model provenance is a
  DSSE-shaped digest bundle verified by native C++, not public Sigstore transparency evidence.
- External k6/locust load confirmation. The native Go full-stack load/SLO gate passes, but neither
  `k6` nor `locust` is installed locally, so PA064 remains partial until one external open-source
  load tool confirms the product path.
- Final UI screenshots/export/accessibility hardening.

## Next Highest-Value Tranche

1. ~~Add Transformers inference for SmolLM2-135M-Instruct.~~ **Done (R1):** real GPU inference behind unchanged contracts via `make llm-real-sample`.
2. Add live AWQ/GPTQ loading, live llama.cpp GGUF generation, and live vLLM variants to extend the current fp16/8-bit/4-bit Pareto report; keep `make llm-quantized-preflight-sample` and `make llm-gguf-preflight-sample` as artifact/runtime sanity gates.
3. Install or document Rust toolchain bootstrap so the gateway rebuilds in CI.
4. Add optional secondary scanner coverage (Grype, pip-audit, gitleaks, osv-scanner) around the now
   passing Trivy-backed live scan.
5. Add live MLflow logging around the promotion pipeline.
6. Run the verified CLIP garment-image/text path across a fixed VTON benchmark and report confidence intervals.
7. Real VTON (CatVTON) execution on the L4 GPU behind the existing VTON contracts.
