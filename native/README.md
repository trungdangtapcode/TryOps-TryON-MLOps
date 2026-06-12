# Native Modules

This folder makes the project stronger than a Python-only ML demo.

## Decision

- Rust is the target production gateway language.
- Go is the target Kubernetes/platform controller language.
- C++ is used for hot metric, policy, preprocessing, energy, burn-rate, online experimentation and experiment statistics, chaos, model-artifact scan, and semantic-cache lookup paths.
- Go is used for platform/control-plane services and the deterministic LLM guardrail CLI.
- Python remains the ML research, training, evaluation, and pipeline glue layer.

## Rust Gateway

Path: `native/rust/tryops-gateway`

Purpose:

- API gateway and request boundary.
- `/api/*` reverse proxy to the backend `/v1/*` contract with request-ID propagation.
- Auth, request validation, native rate limits, payload limits, timeouts, tracing, and signed-artifact preflight policy.
- Native quota pre-admission for LLM/VTON request and token usage.
- Calls vLLM, KServe, Triton, MLflow, and artifact services.

Source layout:

- `src/main.rs`: thin binary entrypoint, tracing, CLI dispatch, and Axum server boot.
- `src/handlers.rs`: HTTP routes for health, metrics, promotion preflight, quota, and `/api/*`.
- `src/proxy.rs`: backend `/v1/*` mapping, request IDs, header policy, and upstream response bridging.
- `src/trace_context.rs`: W3C `traceparent` parsing/generation and gateway trace-response headers.
- `src/trace_envelope.rs`: shared native trace/log envelope construction and validation for gateway requests.
- `src/guardrail.rs`: Rust edge callout to the Go LLM guardrail sidecar.
- `src/semantic_cache.rs`: Rust edge cache admission plus optional C++ semantic-cache lookup bridge.
- `src/quota.rs`: native quota ledger plus `quota-check` batch CLI contract.
- `src/quota_store.rs`: optional `TRYOPS_GATEWAY_QUOTA_LEDGER_PATH` file-backed ledger persistence.
- `src/quota_durable.rs`: optional Postgres usage upsert and Valkey-compatible counter mirrors.
- `src/quota_snapshot.rs`: hashed tenant usage snapshots for the BFF/dashboard read model.
- `src/rate_limit.rs`: per-key minute limiter and hashed rate-limit identity.
- `src/metrics.rs`: Prometheus request, latency, quota, guardrail, rate-limit, upstream, and inflight metrics.
- `src/tls.rs`: optional axum-server/rustls HTTPS listener configuration from certificate/key paths.
- `src/state.rs`, `src/config.rs`, `src/errors.rs`, `src/cli.rs`: runtime state, env parsing, error envelopes, and HTTP/HTTPS healthcheck CLI.

Expected command when Rust is installed:

```bash
cd native/rust/tryops-gateway
cargo run
```

Verified commands:

```bash
make native-rust-build
make native-rust-test
make native-rust-smoke
make native-edge-guardrail-smoke
make native-edge-cache-smoke
make native-quota-ledger-smoke
make native-trace-envelope-sample
make native-tls-contract-sample
make native-tls-smoke
make quota-sample
```

Integration:

- `POST /v1/quota/check` and `GET /v1/quota/snapshot` run the quota ledger inside Axum/Tokio.
- `TRYOPS_GATEWAY_QUOTA_LEDGER_PATH` makes the gateway and `quota-check` CLI load and persist the
  native quota ledger to a local JSON file for single-node durability evidence.
- `TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN` mirrors accepted usage into Postgres `tryops_quota_usage`;
  `TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR` mirrors accepted increments to Valkey-compatible counters.
- `GET|POST /api/*` forwards to the configured `TRYOPS_GATEWAY_UPSTREAM` as `/v1/*`, while admin promotion/model routes require `x-tryops-artifact-signed: true`.
- `GET /api/auth/session` maps to `/v1/auth/session` and is preflighted with `session:read` so the
  Console can render viewer/operator/admin navigation from a server-side RBAC session contract.
- `TRYOPS_GATEWAY_SEMANTIC_CACHE_CLI` plus `TRYOPS_GATEWAY_SEMANTIC_CACHE_ENTRIES`
  let the Rust edge invoke the native C++ semantic-cache CLI before proxying LLM generation.
  The gateway emits `x-tryops-edge-cache-lookup-*` response headers and
  `tryops_gateway_semantic_cache_lookups_total` metrics for hit/miss/error outcomes.
- `GET /metrics` exposes native Prometheus text for gateway request totals, latency histogram buckets, quota decisions, rate-limit rejects, upstream errors, and in-flight proxy requests.
- `TRYOPS_GATEWAY_STRUCTURED_LOG_PATH` writes `tryops.native_trace_log_envelope.v1` JSONL for proxied requests so the OpenTelemetry Collector filelog receiver can ingest gateway events without Python.
- `TRYOPS_GATEWAY_TLS_CERT_PATH` and `TRYOPS_GATEWAY_TLS_KEY_PATH` switch the listener from plaintext
  HTTP to native rustls HTTPS. The optional Compose `gateway-tls` profile mounts these values from
  `tryops_tls_cert` and `tryops_tls_key` secrets.
- `tryops-gateway quota-check` exposes the same quota engine as a batch CLI for reproducible local artifacts.
- `tryops-gateway health-check` verifies the running gateway from inside the container healthcheck;
  set `TRYOPS_GATEWAY_HEALTH_SCHEME=https` and `TRYOPS_GATEWAY_HEALTH_INSECURE=true` for local
  self-signed TLS smoke checks.
- `src/tryops/quota.py` delegates to `TRYOPS_QUOTA_GATEWAY_URL` when the Rust gateway is available, then falls back to the deterministic Python ledger.

Current binary:

```text
artifacts/native/tryops-gateway
```

## Go Quota Read Model

Path: `native/go/tryops-quota-read-model`

Purpose:

- Dependency-free Go report generator for quota/accounting read models.
- Consumes Rust gateway quota usage/snapshot evidence from `artifacts/eval/quota/quota_usage.json`.
- Emits `tryops.native_quota_read_model.v1` with hashed tenants, limits, remaining capacity,
  utilization, risk, and showback fields for the BFF and Console Dashboard.
- Carries research links for FinOps allocation/showback, Valkey hot counters, and Postgres durable
  upserts.

Main files:

- `config.go`: CLI flag parsing and default input/output paths.
- `load.go`: typed JSON loading for quota simulation and native batch inputs.
- `model.go`: tenant grouping, plan inference, utilization, risk, and showback logic.
- `pricing.go`: deterministic per-dimension unit prices.
- `report.go`: JSON report writer.
- `types.go`: schema structs for input and output contracts.
- `model_test.go`: model and privacy checks.

Verified commands:

```bash
make native-quota-read-model-test
make native-quota-read-model-sample
```

Current binary:

```text
artifacts/native/tryops_quota_read_model
```

## Go Controller

Path: `native/go/tryops-controller`

Purpose:

- Platform reconciler for model candidates and deployment aliases.
- Future home for a Kubernetes controller built with controller-runtime or Kubebuilder.
- Watches promotion decisions and syncs KServe/registry state.
- Verifies signed GitHub-style promotion PR webhooks before accepting merged PR evidence and promotion actions.
- Verifies signed MLflow-style registry webhooks and converts accepted alias events into GitOps sync plus canary rollout actions.

Source layout:

- `main.go`: thin binary entrypoint.
- `server.go`: route registration, middleware, JSON responses, and env parsing.
- `handlers.go`: health, reconcile, registry webhook, and GitHub PR webhook handlers.
- `signature.go`: MLflow/GitHub HMAC signature validation and freshness checks.
- `promotion.go`: registry and signed-PR promotion decision logic.
- `fields.go`: typed extraction helpers for webhook payloads.
- `types.go`: request/response contracts.

Verified commands:

```bash
make native-go-build
make native-go-test
make native-go-smoke
make signed-pr-promotion-sample
make registry-webhook-sample
```

Current binary:

```text
artifacts/native/tryops-controller
```

## Go Config Contract Gate

Path: `native/go/tryops-config-contract`

Purpose:

- Parses `docker-compose.yml` with a real YAML parser.
- Validates enterprise service presence, env vars, Compose secret declarations/mounts, direct
  credential-env absence, `.env.example` coverage, port interpolations, healthchecks, readiness
  dependency conditions, named volumes, and Rust gateway env references.
- Emits `tryops.native_config_contract.v1` so config drift becomes CI evidence instead of an
  undocumented deployment surprise.

Verified commands:

```bash
make native-config-contract-test
make native-config-contract-sample
```

Current binary:

```text
artifacts/native/tryops_config_contract
```

## Go Dependency Lock Contract Gate

Path: `native/go/tryops-dependency-lock-contract`

Purpose:

- Validates PA063 dependency-lock evidence across Python, Node, Rust, and Go without Python runtime
  scripts.
- Checks `uv.lock` covers every dependency declared in `pyproject.toml`, including the
  accelerate/bitsandbytes ML packages that previously drifted during benchmark runs.
- Checks `web/package-lock.json` locks Console direct dependencies with integrity metadata.
- Checks Rust gateway `Cargo.lock` covers direct `Cargo.toml` dependencies for the compiled edge
  binary.
- Checks every native Go module with external requirements has matching `go.sum` checksum coverage.
- Emits `tryops.native_dependency_lock_contract.v1` for the Console evidence registry.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: root and lockfile path flags.
- `files.go`: rooted JSON/text loading and report writing helpers.
- `python.go`: `pyproject.toml` dependency extraction and `uv.lock` package/hash checks.
- `node.go`: `package.json` and `package-lock.json` direct dependency checks.
- `rust.go`: Rust gateway `Cargo.toml`/`Cargo.lock` checks.
- `golang.go`: native Go `go.mod`/`go.sum` checksum coverage checks.
- `report.go`, `types.go`: evidence output and summary contracts.
- `dependency_lock_test.go`: temp-root regression coverage for all ecosystems.

Verified commands:

```bash
make native-dependency-lock-contract-test
make native-dependency-lock-contract-sample
```

Current binary:

```text
artifacts/native/tryops_dependency_lock_contract
```

## Go Secret Rotation Contract Gate

Path: `native/go/tryops-secret-rotation-contract`

Purpose:

- Validates the PA060 Vault/workload-identity and key-rotation plan from
  `configs/secret_rotation_policy.json`.
- Checks hash-only API-key registry storage, rotation/overlap windows, managed secret ownership,
  Compose secret coverage, `.env.example` live identity variables, and Kubernetes manifests.
- Parses Vault `SecretStore` and `ExternalSecret` YAML to prove External Secrets coverage for
  runtime env vars without committing secret values.
- Verifies a non-automounted `tryops-runtime` ServiceAccount plus projected service-account token
  settings for Vault auth.
- Emits `tryops.native_secret_rotation_contract.v1` for the Console evidence registry.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: root/policy/compose/env/output flags.
- `files.go`: rooted JSON/YAML/text loading and report writing helpers.
- `policy.go`: provider, workload identity, managed secret, and rotation-window checks.
- `registry.go`: hash-only API-key registry and break-glass checks.
- `compose.go`: Compose secret declarations, service mounts, and `.env.example` coverage.
- `kubernetes.go`: Vault `SecretStore`, `ExternalSecret`, ServiceAccount, and projected-token checks.
- `report.go`, `types.go`: evidence output and summary contracts.
- `secret_rotation_test.go`: temp-root regression coverage for the contract and invalid key hashes.

Verified commands:

```bash
make native-secret-rotation-contract-test
make native-secret-rotation-contract-sample
```

Current binary:

```text
artifacts/native/tryops_secret_rotation_contract
```

## Go Postgres Migration Gate

Path: `native/go/tryops-db-migrator`

Purpose:

- Loads versioned SQL migrations from `infra/postgres/migrations`.
- Validates idempotent product/quota DDL for requests, feedback, jobs, models, audit logs, and
  native quota usage.
- Uses `github.com/jackc/pgx/v5/pgxpool` for live Postgres apply mode.
- Records migration checksums in `tryops_schema_migrations` and verifies live tables after apply.
- Emits `tryops.native_postgres_migration.v1` for the Console evidence registry.

Verified commands:

```bash
make native-db-migrator-test
make native-db-migrator-sample
TRYOPS_POSTGRES_MIGRATION_DSN=postgres://tryops:tryops@127.0.0.1:15432/tryops?sslmode=disable make native-db-migrator-apply
```

Current binary:

```text
artifacts/native/tryops_db_migrator
```

## Go Backup Restore Drill

Path: `native/go/tryops-backup-restore`

Purpose:

- Validates Compose Postgres/MinIO storage, named volumes, secrets, restore isolation, and
  `infra/backup/restore_drill.cron`.
- Uses the Postgres container's matching `pg_dump`/`pg_restore`/`psql` tools for live drills.
- Restores Postgres into the isolated `tryops_restore_drill` database and compares table row counts.
- Uses MinIO `mc mirror` inside the MinIO container to prove object backup and restore into
  `tryops-restore-drill`.
- Emits `tryops.native_backup_restore_drill.v1` for the Console evidence registry.

Verified commands:

```bash
make native-backup-restore-test
make native-backup-restore-sample
TRYOPS_POSTGRES_BACKUP_DSN=postgres://tryops:tryops@127.0.0.1:15432/tryops?sslmode=disable make native-backup-restore-live
```

Current binary:

```text
artifacts/native/tryops_backup_restore
```

## Go TLS Contract Gate

Path: `native/go/tryops-tls-contract`

Purpose:

- Parses `docker-compose.yml` with a real YAML parser and validates the optional `gateway-tls`
  production profile.
- Confirms TLS cert/key secret mounts, HTTPS healthcheck env, gateway TLS env paths, and TLS port
  interpolation.
- Validates a local SAN certificate/key pair for localhost smoke evidence.
- In live mode, performs a TLS handshake against the Rust gateway, checks HTTPS `/health`, and proves
  plaintext HTTP is rejected on the TLS port.
- Emits `tryops.native_tls_contract.v1` for the Console evidence registry.

Verified commands:

```bash
make native-tls-contract-test
make native-tls-contract-sample
make native-tls-smoke
```

Current binary:

```text
artifacts/native/tryops_tls_contract
```

## Go Container Image Contract Gate

Path: `native/go/tryops-container-contract`

Purpose:

- Validates the PA084 split-image contract from `configs/container_images.json`.
- Parses `docker-compose.yml` with a real YAML parser and checks each required image role has a
  matching Compose service, build context, and Dockerfile.
- Checks Dockerfiles for multi-stage native builds, non-SDK runtime stages, source-path coverage,
  and role coverage for gateway, controller, guardrail, benchmark, C++ tools, API, and web assets.
- Emits `tryops.native_container_contract.v1` so container drift is CI evidence instead of a
  deployment surprise.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: root/manifest/compose/output flags.
- `load.go`: JSON manifest and Compose YAML loading.
- `dockerfile.go`: Dockerfile stage/base parsing helpers.
- `evaluator.go`: role, source, Dockerfile, and Compose checks.
- `report.go`, `types.go`: report output and contracts.
- `evaluator_test.go`: repository contract and missing-role regression coverage.

Verified commands:

```bash
make native-container-contract-test
make native-container-contract-sample
docker compose config
```

Current binary:

```text
artifacts/native/tryops_container_contract
```

## Go CI Supply-Chain Contract Gate

Path: `native/go/tryops-ci-contract`

Purpose:

- Dependency-free Go validator for the PA062 `make ci` and GitHub Actions supply-chain contract.
- Checks `.github/workflows/ci.yml` for Python/Node/Go/Rust/C++ test wiring, Compose validation,
  artifact upload, seven-image Docker Buildx matrix, Syft SPDX SBOM generation, Trivy
  HIGH/CRITICAL scan gating, and Cosign keyless signing on non-PR pushes.
- Checks `Makefile` for the local `ci` mirror and `native-ci-contract-*` targets.
- Cross-checks vulnerability, supply-chain, and container-contract report schemas.
- Records local required-tool availability for Docker, Syft, Trivy, and Cosign without treating
  missing external tools as successful production evidence.
- Emits `tryops.native_ci_contract.v1` for the Console evidence registry.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: root/workflow/Makefile/evidence/output flags.
- `workflow.go`: GitHub Actions CI, image, SBOM, scan, upload, and signing checks.
- `makefile.go`: local `make ci` and native contract target checks.
- `tools.go`: local Docker/Syft/Trivy/Cosign discovery.
- `evidence.go`: referenced report schema and readiness checks.
- `evaluate.go`, `files.go`, `types.go`: report assembly and JSON emission.
- `ci_contract_test.go`: workflow and partial-readiness regression coverage.

Verified commands:

```bash
make native-ci-contract-test
make native-ci-contract-sample
```

Current binary:

```text
artifacts/native/tryops_ci_contract
```

## Go Performance Budget Gate

Path: `native/go/tryops-performance-budget`

Purpose:

- Dependency-free CI gate that turns native performance evidence into one pass/fail budget report.
- Consumes the Rust gateway benchmark, Go SLO gate, Go config contract, C++ perf stats, and native
  binary artifacts.
- Checks Rust gateway p95/p99/RPS/speedup budgets, full edge-proxy overhead, Go gate pass status,
  C++ perf SLOs, and executable native binary presence.
- Emits `tryops.native_performance_budget.v1` JSON plus a Markdown summary suitable for
  `GITHUB_STEP_SUMMARY` and artifact upload.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: flags and CI output defaults.
- `load.go`: typed artifact loading with missing-artifact reporting.
- `evaluator.go`: Rust/Go/C++ budget checks and failure messages.
- `markdown.go`: CI summary rendering.
- `types.go`, `jsonutil.go`: report contracts and JSON/path helpers.
- `evaluator_test.go`: complete, missing-artifact, and regression-failure coverage.

Verified commands:

```bash
make native-performance-budget-test
make native-performance-budget-sample
```

Current binary:

```text
artifacts/native/tryops_performance_budget
```

## Go Trace Envelope Gate

Path: `native/go/tryops-trace-envelope`

Purpose:

- Dependency-free native validator/report generator for the shared trace/log envelope contract.
- Validates W3C `traceparent`, non-zero lowercase hex trace/span IDs, trace flags, service resource
  identity, event/severity fields, and sanitized attributes.
- Requires Rust, Go, C++, and FastAPI envelopes before the report can pass.
- Emits `tryops.native_trace_envelope.v1` with research links to W3C Trace Context and OpenTelemetry
  log/resource conventions.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: input/output flags.
- `load.go`: JSON envelope array/object loading.
- `validate.go`: shared contract validation and sensitive-attribute rejection.
- `samples.go`: native Go sample envelope.
- `report.go`: aggregate coverage report.
- `types.go`: envelope/report contracts.
- `validator_test.go`: validator and coverage tests.

Verified commands:

```bash
make native-trace-envelope-test
make native-trace-envelope-sample
```

Current binary:

```text
artifacts/native/tryops_trace_envelope
```

## Go Observability Contract Gate

Path: `native/go/tryops-observability-contract`

Purpose:

- Validates the OpenTelemetry Collector, Compose, Prometheus, and trace/log correlation contract.
- Checks `infra/otel/collector.yml` for OTLP gRPC/HTTP receivers, JSONL filelog ingestion,
  memory/resource/batch processors, trace/log/metric file exporters, health extension, and three
  service pipelines.
- Checks `docker-compose.yml` for the `otel-collector` service and Prometheus dependency, and
  checks `infra/prometheus/prometheus.yml` for the Collector scrape target.
- Reads gateway JSONL envelopes, API spans, and API structured logs to prove shared trace IDs,
  service identity, model-call metadata, native envelopes, and sensitive-payload redaction.
- Emits `tryops.native_observability_contract.v1`.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: root/config/input/output flags.
- `collector.go`, `compose.go`, `prometheus.go`: parsed config checks.
- `correlation.go`: gateway/API trace-log correlation checks.
- `yamlutil.go`, `jsonl.go`, `stringutil.go`: parser helpers.
- `evaluate.go`, `report.go`, `types.go`: report assembly and contracts.
- `observability_test.go`: fixture-based contract regression coverage.

Verified commands:

```bash
make native-observability-contract-test
make native-observability-contract-sample
```

Current binary:

```text
artifacts/native/tryops_observability_contract
```

## Go Alertmanager Contract Gate

Path: `native/go/tryops-alertmanager-contract`

Purpose:

- Validates the local Alertmanager and Prometheus alert routing contract.
- Checks `infra/alertmanager/alertmanager.yml` for page/ticket receivers, severity matchers,
  alertname/workload/severity grouping, inhibition, and the Go controller webhook target.
- Checks `infra/prometheus/prometheus.yml` for `alertmanager:9093` forwarding and rule files.
- Parses all Prometheus rule files to prove alert coverage for latency, quality, SLO burn-rate, and
  FinOps alerts across page/warning/ticket severities.
- Checks `docker-compose.yml` for the Alertmanager service, healthcheck, config volume, storage
  volume, host port interpolation, and Prometheus dependency.
- Emits `tryops.native_alertmanager_contract.v1`.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: root/config/output flags.
- `alertmanager.go`, `prometheus.go`, `compose.go`: parsed config checks.
- `yamlutil.go`: shared YAML helpers.
- `evaluate.go`, `report.go`, `types.go`: report assembly and contracts.
- `alertmanager_test.go`: fixture-based routing regression coverage.

Verified commands:

```bash
make native-alertmanager-contract-test
make native-alertmanager-contract-sample
```

Current binary:

```text
artifacts/native/tryops_alertmanager_contract
```

## Go LLM Guardrail Sidecar And CLI

Path: `native/go/tryops-guardrail`

Purpose:

- Dependency-free native classifier for LLM ingress and egress guardrail checks.
- Detects prompt injection, system-prompt leakage, secret disclosure, unbounded consumption, unsafe agency, PII-like input, and credential-like output.
- Runs as an HTTP sidecar for Rust gateway edge enforcement and API gating, and as a stdin/stdout CLI for batch/offline evaluation.
- Emits `tryops.native_guardrail.v1` JSON without cgo or Python-native extension coupling.

Source layout:

- `main.go`: thin serve/CLI dispatch.
- `server.go`: HTTP sidecar routes, middleware, metrics endpoint, and env parsing.
- `cli.go`: stdin/stdout batch contract.
- `evaluator.go`: deterministic guardrail classifier and OWASP risk aggregation.
- `metrics.go`: Prometheus counters for decisions and findings.
- `types.go`: request/response contracts.

Verified commands:

```bash
make guardrail-sample
make native-guardrail-test
make native-guardrail-smoke
make native-edge-guardrail-smoke
```

Integration:

- `src/tryops/guardrails.py` calls `TRYOPS_GUARDRAIL_URL` first, then `artifacts/native/tryops_guardrail_cli`, then the deterministic Python fallback.
- The Rust gateway calls `TRYOPS_GATEWAY_GUARDRAIL_URL` before proxying `/api/llm/generate`, so blocked prompts do not reach Python.
- `scripts/evaluate_guardrails.py` writes `tryops.guardrail_report.v1`.
- `/v1/llm/generate` enforces the verdict before generation and validates output before returning it.
- `docker-compose.yml` runs the sidecar as `guardrail` and Prometheus scrapes its native metrics.

Current binary:

```text
artifacts/native/tryops_guardrail_cli
```

## Go Benchmark Load Driver

Path: `native/go/tryops-benchmark`

Purpose:

- Dependency-free Go stdlib load generator and benchmark orchestrator.
- Removes the Python/GIL load-driver limitation from the gateway-vs-FastAPI serving benchmark.
- Starts FastAPI and the compiled Rust gateway, warms both targets, and drives keep-alive HTTP load.
- Measures identical `GET /health`, direct validated `POST /v1/promotion/evaluate`, and full edge `POST /api/promotion/evaluate` proxy traffic.
- Emits `tryops.native_gateway_benchmark.v1`.

## Go Full-Stack Load SLO Driver

Path: `native/go/tryops-fullstack-load`

Purpose:

- Dependency-free Go stdlib full-stack load driver for the product gateway/BFF path.
- Starts FastAPI plus the compiled Rust gateway on local high ports and drives traffic through
  `/api/*` rather than bypassing the edge.
- Exercises six production-facing scenarios: gateway health, RBAC session, evaluation summary,
  quota summary, LLM generation, and operator promotion gate.
- Applies per-scenario error-rate, p95/p99 latency, and RPS SLOs, then records k6/locust
  availability for external confirmation.
- Emits `tryops.native_fullstack_load.v1` for the Console evaluation index.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: flags, environment defaults, and repo-root paths.
- `process.go`: managed FastAPI/gateway subprocess lifecycle and readiness checks.
- `scenarios.go`, `payloads.go`: product traffic definitions and signed promotion payloads.
- `loadgen.go`: worker pool, keep-alive HTTP client, percentiles, and throughput summaries.
- `slo.go`: scenario SLO policies and verdicts.
- `external.go`: k6/locust detection and optional external-tool requirement.
- `evaluate.go`, `report.go`, `types.go`: report assembly and JSON emission.
- `fullstack_load_test.go`: SLO, scenario, and report regressions.

Verified commands:

```bash
make native-fullstack-load-test
make native-fullstack-load-sample
```

Current binary:

```text
artifacts/native/tryops_fullstack_load
```

## Go SLO Regression Gate

Path: `native/go/tryops-slo-gate`

Purpose:

- Dependency-free CI gate for native benchmark regressions.
- Consumes `tryops.native_gateway_benchmark.v1` from `native/go/tryops-benchmark`.
- Fails nonzero on error, p95/p99 latency, throughput, or edge-proxy overhead regressions.
- Emits `tryops.native_slo_gate.v1` evidence for the Console evaluation index.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: flags and environment defaults.
- `load.go`: benchmark and optional policy JSON loading.
- `policy.go`: default SLO/regression thresholds.
- `gate.go`: rule evaluation and failure messages.
- `report.go`: report emission and CLI summary.
- `types.go`: benchmark, policy, and report contracts.
- `gate_test.go`: pass/fail regression coverage.

Verified commands:

```bash
make native-slo-gate-test
make native-slo-gate-sample
```

Current binary:

```text
artifacts/native/tryops_slo_gate
```

## Go Event Dispatcher

Path: `native/go/tryops-event-dispatcher`

Purpose:

- Dependency-free native dispatcher for promotion, feedback, incident, and quota events.
- Validates CloudEvents-style required fields (`specversion`, `id`, `source`, `type`, `time`, and JSON data).
- Writes appendable `tryops.native_audit_event.v1` JSONL audit records.
- Signs webhook payloads with HMAC-SHA256 and retries transient delivery failures.
- Emits `tryops.native_event_dispatcher.v1` governance evidence for the Console evaluation index.

Source layout:

- `main.go`: thin CLI entrypoint.
- `config.go`: flags and environment defaults.
- `events.go`: supported event types, normalization, validation, and sample events.
- `load.go`: JSON array and JSONL event loading.
- `audit.go`: audit JSONL sink.
- `signature.go`: HMAC-SHA256 signing and verification.
- `webhook.go`: signed webhook delivery with retry.
- `sample.go`: local signed webhook receiver for reproducible evidence.
- `dispatcher.go`, `report.go`, `types.go`: fanout, report emission, and contracts.
- `dispatcher_test.go`: audit, signature, retry, and validation coverage.

Verified commands:

```bash
make native-event-dispatcher-test
make native-event-dispatcher-sample
```

Current binary:

```text
artifacts/native/tryops_event_dispatcher
```

Source layout:

- `main.go`: thin CLI flag parsing and report write.
- `benchmark.go`: scenario orchestration and speedup calculations.
- `process.go`: managed FastAPI/gateway subprocess lifecycle and readiness checks.
- `loadgen.go`: worker pool, keep-alive HTTP client, latency percentiles, and throughput summaries.
- `payloads.go`: validated promotion benchmark payloads.
- `report.go`: JSON artifact writer and CLI summary.
- `types.go`: benchmark contracts.

Verified commands:

```bash
make native-benchmark-build
make native-benchmark-test
make gateway-benchmark-native
```

Current binary:

```text
artifacts/native/tryops_benchmark
```

## C++ Trace Envelope Validator

Path: `native/cpp/tryops_trace_envelope`

Purpose:

- Dependency-free native C++ validator for the shared trace/log envelope contract.
- Keeps W3C trace ID/span ID/flags validation and service resource checks in reusable header/source
  code with a thin CLI adapter.
- Gives the Go aggregate report a compiled C++ proof point without adding a JSON library dependency.

Verified commands:

```bash
make native-trace-envelope-cpp-test
make native-trace-envelope-sample
```

Current verified binary:

```text
artifacts/native/tryops_trace_envelope_cli
```

## C++ Policy Engine

Path: `native/cpp/tryops_policy`

Purpose:

- Verified dependency-free native policy engine.
- Mirrors the Python promotion gate.
- Useful as a future high-performance library or WASM/native extension candidate.

Verified commands:

```bash
make native-cpp-test
make native-policy-sample
```

Integration:

- `native/cpp/tryops_policy/src/tryops_policy_cli.cpp` exposes the native engine as a small CLI.
- `src/tryops/native_policy.py` serializes Python candidates into a stable line-based wire format.
- `scripts/evaluate_native_policy.py` compares native and Python decisions.
- `scripts/run_local_promotion_pipeline.py` writes `native_policy_decision.json` when the CLI is available.

Current verified binary:

```text
artifacts/native/tryops_policy_cli
```

## C++ Online Experiment Router

Path: `native/cpp/tryops_experiment_router`

Purpose:

- Keeps A/B bucketing, holdback, guardrail filtering, and UCB-style bandit allocation on the compiled production boundary.
- Blocks variants whose guardrail block rate, latency p95, or error rate exceed configured thresholds.
- Emits `tryops.native_experiment_router.v1` JSON for auditable routing decisions.

Verified command:

```bash
make experiment-routing-sample
```

Integration:

- `src/tryops/native_experiment_router.py` marshals model-variant metrics into `artifacts/native/tryops_experiment_router_cli`.
- `src/tryops/routing.py` exposes `build_experiment_routing_decision` beside the existing direct/canary router.
- `scripts/evaluate_online_experimentation.py` writes `tryops.online_experiment_report.v1`, proving guarded A/B routing and a bandit shift to the stronger challenger.

Current verified binary:

```text
artifacts/native/tryops_experiment_router_cli
```

## C++ Online Experiment Statistics

Path: `native/cpp/tryops_experiment_stats`

Purpose:

- Computes holdback-vs-variant uplift, relative uplift, and Agresti-Caffo adjusted confidence intervals.
- Computes Wald-style SPRT log-likelihood ratios and early-stop verdicts for online experiments.
- Emits `tryops.native_experiment_stats.v1` JSON for auditable experiment decisions.

Verified command:

```bash
make experiment-analysis-sample
```

Integration:

- `src/tryops/native_experiment_stats.py` marshals aggregate holdback and variant metrics into `artifacts/native/tryops_experiment_stats_cli`.
- `scripts/evaluate_online_experiment_analysis.py` combines native experiment stats with native Theme-N bootstrap CI evidence from `tryops_eval_stats`.
- `artifacts/eval/experiments/online_experiment_analysis_report.json` records holdback uplift, CI, and sequential early-stop checks.

Current verified binary:

```text
artifacts/native/tryops_experiment_stats_cli
```

## C++ Model Artifact Scanner

Path: `native/cpp/tryops_model_scan`

Purpose:

- Enforces a SafeTensors-only model artifact policy before promotion.
- Rejects pickle-family formats such as `.bin`, `.pt`, `.pth`, `.ckpt`, `.pkl`, `.pickle`, and `.joblib`.
- Validates the SafeTensors header shape without importing Python ML frameworks or deserializing untrusted files.
- Feeds model-artifact scan metadata into both Python and native C++ promotion gates.

Verified command:

```bash
make model-supply-chain-sample
```

Integration:

- `src/tryops/native_model_scan.py` calls `artifacts/native/tryops_model_scan_cli` and falls back only for local deterministic tests.
- `scripts/evaluate_model_supply_chain.py` writes `tryops.model_supply_chain_report.v1`.
- `src/tryops/policy.py`, `native/cpp/tryops_policy`, and `policies/model_promotion.rego` require a passing scan for VTON and LLM candidates.

Current verified binary:

```text
artifacts/native/tryops_model_scan_cli
```

## C++ Model Provenance Verifier

Path: `native/cpp/tryops_model_provenance`

Purpose:

- Verifies the model artifact digest against the signed subject in the local DSSE-shaped bundle.
- Verifies the payload digest, signer identity, and SLSA provenance predicate type.
- Emits `tryops.native_model_provenance.v1` so promotion can reject unsigned or tampered weights
  before load.
- Keeps the offline evidence contract compatible with future OpenSSF Model Signing / Sigstore
  model-transparency bundles without claiming local keyless OIDC.

Verified command:

```bash
make model-supply-chain-sample
```

Integration:

- `src/tryops/model_provenance.py` writes `tryops.model_provenance.v1`, an in-toto/SLSA statement,
  and `model_signature_bundle.json`.
- `scripts/evaluate_model_supply_chain.py` invokes the native verifier before evaluating promotion.
- `src/tryops/policy.py`, `native/cpp/tryops_policy`, and `policies/model_promotion.rego` require a
  passing provenance verification for VTON and LLM candidates.

Current verified binary:

```text
artifacts/native/tryops_model_provenance_cli
```

## C++ OpenLineage Validator

Path: `native/cpp/tryops_openlineage`

Purpose:

- Provides a compiled validation boundary for OpenLineage-standard RunEvent artifacts.
- Checks the event state, event time, UUID-shaped run ID, job namespace/name, producer, RunEvent schema URL, and input/output dataset sections.
- Emits `tryops.native_openlineage.v1` so deployment evidence can prove the standard lineage event was checked outside Python.

Verified command:

```bash
make pipeline-sample
```

Integration:

- `src/tryops/lineage.py` maps internal TryOps lineage into `openlineage_run_event.json`.
- `src/tryops/native_openlineage.py` calls `artifacts/native/tryops_openlineage_cli` and falls back to a deterministic structural validator when the binary is absent.
- `src/tryops/deployment.py` embeds the OpenLineage event and validation verdict in deployment manifests.

Current verified binary:

```text
artifacts/native/tryops_openlineage_cli
```

## C++ GitOps Manifest Validator

Path: `native/cpp/tryops_gitops`

Purpose:

- Provides a compiled validation boundary for generated GitOps deployment manifests.
- Checks the Argo CD `Application`, Argo Rollouts `Rollout`, stable/canary `Service` manifests, Kustomization resources, candidate labels, and canary `setWeight`/`pause` steps.
- Emits `tryops.native_gitops.v1` so release evidence proves the GitOps package was checked outside Python.

Verified command:

```bash
make deploy-package-sample
```

Integration:

- `src/tryops/gitops.py` builds Argo CD / Argo Rollouts YAML from the deployment manifest.
- `src/tryops/native_gitops.py` calls `artifacts/native/tryops_gitops_cli` and falls back to a deterministic structural validator when the binary is absent.
- `src/tryops/deployment.py` writes `gitops/` manifests and embeds the validation verdict in `deployment_manifest.json`.

Current verified binary:

```text
artifacts/native/tryops_gitops_cli
```

## C++ Chaos Scenario Evaluator

Path: `native/cpp/tryops_chaos`

Purpose:

- Provides a compiled SRE fault-classification path for chaos drills.
- Covers GPU OOM, slow decode, corrupted weights, and poisoned-candidate scenarios.
- Emits `tryops.native_chaos.v1` with workload, failure mode, expected signal, bad-event count, total-event count, and rollback requirement.
- Feeds the native C++ burn-rate engine so rollback decisions are not made by Python.

Verified command:

```bash
make chaos-sample
```

Integration:

- `src/tryops/native_chaos.py` marshals scenarios into `artifacts/native/tryops_chaos_cli`.
- `src/tryops/chaos.py` evaluates each scenario with `tryops_burn_rate_cli`.
- Page-level chaos burn-rate verdicts reuse `src/tryops/deployment.py` rollback records.

Current verified binary:

```text
artifacts/native/tryops_chaos_cli
```

## C++ Semantic Cache Lookup

Path: `native/cpp/tryops_semantic_cache`

Purpose:

- Provides the compiled hot path for LLM semantic-cache lookup.
- Computes deterministic lexical embeddings and cosine similarity for offline evidence.
- Emits `tryops.native_semantic_cache.v1` with hit/miss, score, matched entry, and saved token/cost/energy metadata.
- Keeps the line-based wire contract that a Rust gateway, C++ sidecar, FAISS process, or Qdrant bridge can preserve in production.

Source layout:

- `include/tryops_semantic_cache.hpp`: reusable core API for payload parsing, tokenization, lookup, and JSON rendering.
- `src/tryops_semantic_cache.cpp`: embedding, cosine ranking, candidate ordering, and artifact rendering.
- `src/tryops_semantic_cache_cli.cpp`: thin stdin/stdout adapter.
- `tests/test_semantic_cache.cpp`: native core regression test.

Verified command:

```bash
make finops-sample
make native-semantic-cache-test
```

Integration:

- `src/tryops/semantic_cache.py` calls `artifacts/native/tryops_semantic_cache_cli` and falls back to the deterministic Python matcher when the binary is absent.
- `/v1/llm/generate` checks the cache after guardrails/quota and before generation.
- `scripts/evaluate_finops.py` writes `tryops.semantic_cache_report.v1` and `tryops.finops_report.v1`.
- The cost/capacity dashboard targets cache hit/savings metrics.

Current verified binary:

```text
artifacts/native/tryops_semantic_cache_cli
```

## C++ Image Metrics

Path: `native/cpp/tryops_image_metrics`

Purpose:

- Verified dependency-free native image metric CLI.
- Computes MSE, PSNR, dHash distance/similarity, and edge-delta proxy from raw RGB payloads.
- Provides low-level evidence for VTON comparison artifacts without PNG or neural dependencies.

Verified command:

```bash
make native-image-metrics-sample
make vton-native-api-sample
```

Integration:

- `src/tryops/native_image_metrics.py` serializes same-size RGB images into the native wire format.
- `scripts/evaluate_native_image_metrics.py` compares Python and native metric outputs.
- `src/tryops/pipelines/vton_comparison.py` includes a native metrics block when the CLI is built.
- `src/tryops/vton_native_bridge.py` invokes the same CLI from `/v1/vton/infer`, stores
  `native_quality_score` in the VTON report, and persists it into the request `quality` field for
  dashboard/request-detail rollups.

Current verified binary:

```text
artifacts/native/tryops_image_metrics_cli
```

## C++ LLM Batch Scheduler

Path: `native/cpp/tryops_batch_scheduler`

Purpose:

- Verified dependency-free native scheduler benchmark for LLM serving.
- Compares request-level static batching with iteration-level continuous batching on the same mixed request stream.
- Emits throughput, p95 latency, waiting time, scheduled decode slots, decode-slot utilization, and pass/fail comparison evidence.
- Keeps scheduling math in C++ while Python only marshals the LLM sensitivity artifact into the native wire format.

Verified command:

```bash
make llm-continuous-batching-sample
```

Integration:

- `src/tryops/native_batch_scheduler.py` serializes arrival, prefill-token, and decode-token arrays into the native line protocol.
- `scripts/evaluate_continuous_batching.py` writes `artifacts/eval/llm_batching/continuous_batching_report.json`.
- The benchmark is local scheduler evidence for continuous batching; a live vLLM server benchmark remains a separate production hardening item.

Current verified binary:

```text
artifacts/native/tryops_batch_scheduler_cli
```

## C++ VTON Advanced Evaluation

Path: `native/cpp/tryops_vton_eval`

Purpose:

- Verified dependency-free native VTON advanced evaluation CLI.
- Computes face-region embedding proxy distance, garment-region masked fidelity, and torso-alignment pose consistency from raw RGB payloads.
- Audits seeded skin-tone and body-type quality slices and emits max-gap pass/fail evidence.
- Fits a Bradley-Terry ranking over the seeded preference-study fixture for principled pairwise comparison evidence.

Verified command:

```bash
make vton-advanced-eval-sample
```

Integration:

- `src/tryops/native_vton_eval.py` serializes person, garment, output, overlay, preference rows, and fairness slices into the native wire format.
- `scripts/evaluate_vton_advanced.py` writes `artifacts/eval/vton_advanced/vton_advanced_eval_report.json`.
- The same script updates the generated VTON model card with identity, masked-fidelity, pose, fairness, Bradley-Terry, and bias/limitation notes.

Current verified binary:

```text
artifacts/native/tryops_vton_eval_cli
```

## C++ VTON Preprocessing

Path: `native/cpp/tryops_vton_preprocess`

Purpose:

- Verified dependency-free native VTON preprocessing CLI.
- Reads raw RGB payloads from Python through a stable line-based wire format.
- Computes foreground coverage, bounding boxes, and rough pose hints as native evidence alongside Python artifact generation.
- Provides native evidence for optional VTON mask and pose preprocessing.

Verified commands:

```bash
make native-vton-preprocess-sample
make vton-preprocess-sample
make vton-native-api-sample
```

Integration:

- `src/tryops/native_vton_preprocess.py` serializes RGB images into the native wire format.
- `scripts/evaluate_native_vton_preprocess.py` exercises the CLI directly.
- `src/tryops/pipelines/vton_preprocessing.py` includes native person and garment evidence in the optional preprocessing report.
- `src/tryops/pipelines/vton_baseline.py` carries the mask, pose, latency, and native evidence into the baseline sidecar.
- `/v1/vton/infer` and async VTON jobs now expose the C++ preprocessing result in
  `native_vton.preprocessing`, persist `native_execution` into the output sidecar, and are verified
  by `artifacts/eval/vton_native_api/vton_native_api_report.json`.

Current verified binary:

```text
artifacts/native/tryops_vton_preprocess_cli
```
