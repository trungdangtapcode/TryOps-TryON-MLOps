# TryOps Console — Production Application Build Plan

> Canonical copy. A summarized copy is embedded in `MLOPS_VTON_LLM_ENTERPRISE_ROADMAP.md` (§Production Application Build Plan).

Date added: 2026-06-11. Research refresh: 2026-06-12. Goal: turn the platform into a **real, runnable enterprise product** an end user actually uses — browser console, backend, database, services, monitoring, dashboard, quota, audit, and incident flow — on top of the existing real LLM (R1/R2), real diffusion VTON, native Rust/Go/C++ boundary, and governance spine.

Current readiness: backend/data/native edge are real; the browser Console is functional but still needs screenshot/export/accessibility hardening, while production Kubernetes External Secrets sync, live OTLP exporters/full traces, and the production runbook are not done yet. The product must stay runnable locally through `make`, with deterministic degraded-mode fallbacks when GPU/network dependencies are unavailable.

### Target architecture

```
              Browser (enterprise users + admins)
                       │ HTTPS
          ┌────────────▼──────────────────────┐
          │ Rust Axum edge                     │
          │ auth preflight · quota/rate/body   │
          │ trace/context · guardrail dispatch │
          │ /api proxy · optional static edge  │
          └────────────┬───────────────┬───────┘
                       │ /api          │ / or /assets
          ┌────────────▼────────────┐  │
          │ FastAPI product BFF      │  │ web/dist static assets
          │ control plane only       │  │ FastAPI StaticFiles local,
          │ real LLM/VTON adapters   │  │ nginx or Rust static profile prod
          └───┬───────────┬─────────┘  │
              │           │            │
   ┌──────────▼──┐  ┌─────▼──────┐     │
   │ LLM serve   │  │ VTON serve │     │
   │ HF/vLLM     │  │ diffusers  │     │
   └─────────────┘  └────────────┘     │
              │                         │
   ┌──────────▼─────────────────────────▼────────────┐
   │ Postgres/SQLite · MinIO · Go controller/guardrail │
   │ C++ policy/cache/eval tools · Prometheus/Grafana  │
   │ OpenTelemetry Collector · CI/SBOM/signing gates   │
   └───────────────────────────────────────────────────┘
```

### Research basis

- Vite supports production static builds with `npm run build`, default `dist`, and backend integration through generated manifests/hashes: https://vite.dev/guide/static-deploy and https://vite.dev/guide/backend-integration
- FastAPI can mount `StaticFiles` as an independent static-file application, which is enough for the local SPA serving profile: https://fastapi.tiangolo.com/tutorial/static-files/
- Axum is a good Rust edge fit because it uses Tower middleware/layers; Tokio provides async networking/runtime primitives for high-concurrency services: https://docs.rs/axum/latest/axum/middleware/index.html and https://tokio.rs/
- Native gateway TLS should terminate inside the Rust edge when cert/key material is supplied, with Compose secrets carrying PEM content and OpenSSL-generated SAN certificates used only for local smoke evidence: https://docs.rs/axum-server/0.8.0/axum_server/tls_rustls/index.html, https://docs.rs/rustls/latest/rustls/crypto/index.html, https://docs.docker.com/compose/how-tos/use-secrets/, and https://docs.openssl.org/master/man1/openssl-req/
- Go remains a good fit for controllers, workers, guardrails, and load tools because standard `net/http` and `context` cover HTTP serving plus cancellation/deadline propagation: https://pkg.go.dev/net/http and https://pkg.go.dev/context
- Docker Compose should use healthchecks plus `depends_on: condition: service_healthy` for real readiness ordering, not only process startup: https://docs.docker.com/compose/how-tos/startup-order/
- Native config contract checks should validate Compose interpolation, `.env.example`, service envs/secrets, healthchecks, and readiness dependencies from parsed YAML rather than line matching: https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/, https://docs.docker.com/compose/how-tos/use-secrets/, and https://pkg.go.dev/gopkg.in/yaml.v3
- Production secret management should use Vault Kubernetes auth or JWT-backed workload identity with short-lived projected service-account tokens, sync only runtime Kubernetes Secrets through External Secrets Operator, and leave room for SPIFFE/SPIRE SVID-based identity in clustered deployments: https://developer.hashicorp.com/vault/docs/auth/kubernetes, https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/, https://external-secrets.io/latest/provider/hashicorp-vault/, and https://spiffe.io/docs/latest/spiffe-about/overview/
- Native Postgres migration/pool evidence should use PostgreSQL idempotent DDL and a real Go connection pool, with plan-mode CI evidence and live apply evidence when a DSN is present: https://www.postgresql.org/docs/current/sql-createtable.html, https://www.postgresql.org/docs/current/libpq-connect.html, and https://pkg.go.dev/github.com/jackc/pgx/v5/pgxpool
- Native backup/restore evidence should run PostgreSQL custom-format dump/restore against an isolated restore database and mirror MinIO objects through a restore bucket/prefix rather than trusting volume presence alone: https://www.postgresql.org/docs/current/app-pgdump.html, https://www.postgresql.org/docs/current/app-pgrestore.html, https://www.postgresql.org/docs/current/backup.html, and https://min.io/docs/minio/linux/reference/minio-mc/mc-mirror.html
- Prometheus scrape configs are the right local metrics contract; Grafana provisioning keeps datasources/dashboards version-controlled: https://prometheus.io/docs/prometheus/latest/configuration/configuration/ and https://grafana.com/docs/grafana/latest/administration/provisioning/
- OpenTelemetry Collector is the right next step for traces/logs/metrics pipelines because receivers, processors, exporters, extensions, and service pipelines are configured centrally: https://opentelemetry.io/docs/collector/configuration/
- W3C Trace Context defines the interoperable `traceparent` wire format and invalid all-zero trace/span identifiers used by the native envelope validators: https://www.w3.org/TR/trace-context/
- OpenTelemetry Logs Data Model gives the common log-envelope fields for trace/span correlation, severity, resource, attributes, and event names: https://opentelemetry.io/docs/specs/otel/logs/data-model/
- OpenTelemetry resource semantic conventions require stable service identity fields such as `service.name` and `service.version` for cross-runtime telemetry: https://opentelemetry.io/docs/specs/semconv/resource/
- Postgres enterprise profile needs tested dump/restore; PostgreSQL documents `pg_dump`/`pg_restore` and backup strategy tradeoffs: https://www.postgresql.org/docs/current/app-pgdump.html and https://www.postgresql.org/docs/current/backup.html
- Valkey/Redis-compatible `INCR`/`EXPIRE` counters are the right open-source hot-path primitive for quota and budget windows, with Postgres `INSERT ... ON CONFLICT DO UPDATE` as the durable billing/showback ledger: https://valkey.io/commands/incr/ and https://www.postgresql.org/docs/current/sql-insert.html
- Native performance budgets should be treated as CI evidence: SLO/error-budget practice gives the threshold model, while GitHub Actions job summaries and uploaded artifacts give reviewers a durable JSON+Markdown record of every Rust/Go/C++ budget row: https://sre.google/sre-book/service-level-objectives/ and https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts and https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions
- Full-stack load evidence should be native-first so the product path is measured without Python load-driver bias, then optionally confirmed with open-source external tools that support performance/load workflows and headless execution such as k6 and Locust: https://pkg.go.dev/net/http, https://grafana.com/docs/k6/latest/, and https://docs.locust.io/en/stable/
- Container images should be split with multi-stage Dockerfiles that separate SDK/build stages from smaller runtime images, then wired through explicit Compose `build.context`/`build.dockerfile` entries and CI metadata/provenance capture: https://docs.docker.com/build/building/multi-stage/, https://docs.docker.com/compose/compose-file/build/, and https://docs.docker.com/build/metadata/
- MinIO can serve generated outputs through time-limited presigned object URLs: https://docs.min.io/aistor/developers/sdk/python/api/
- KServe/vLLM is the cluster-grade target for open-source LLM serving once the local product slice is proven: https://kserve.github.io/website/docs/model-serving/generative-inference/overview and https://docs.vllm.ai/en/latest/deployment/integrations/kserve/
- Supply-chain gates should use open-source scanner/signing tools when installed: Syft for SBOMs, Trivy for vulnerability/misconfig/secret scans, Cosign for keyless image signing, GitHub OIDC for signing identity, uploaded artifacts for durable evidence, and Docker Buildx metadata/SBOM/provenance capture in CI: https://github.com/anchore/syft, https://trivy.dev/docs/latest/target/filesystem/, https://docs.sigstore.dev/cosign/signing/signing_with_containers/, https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect, https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts, and https://docs.docker.com/build/ci/github-actions/
- Dependency-lock evidence should be generated from first-party ecosystem lockfiles: `uv.lock` for Python project resolution, `package-lock.json` plus `npm ci` for the Console, `Cargo.lock` for the Rust gateway binary, and Go `go.mod`/`go.sum` checksums for native modules: https://docs.astral.sh/uv/concepts/projects/sync/, https://docs.npmjs.com/cli/v8/configuring-npm/package-lock-json/, https://docs.npmjs.com/cli/v8/commands/npm-ci, https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html, and https://go.dev/ref/mod
- Incident evidence should be native-first and based on open standards: OpenTelemetry log/exception fields for fingerprinted error events, Alertmanager webhook payloads as the incident trigger, SRE blameless postmortem practice for the template, and an optional open-source GlitchTip/Sentry-compatible DSN for external error tracking: https://opentelemetry.io/docs/specs/otel/logs/data-model/, https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-spans/, https://prometheus.io/docs/alerting/latest/configuration/#webhook_config, https://sre.google/sre-book/postmortem-culture/, and https://glitchtip.com/documentation/
- Native content-safety should combine deterministic input/output filtering with stronger model-based classifiers when available; OWASP LLM01 frames prompt injection mitigations around input validation, output filtering, and structured validation, while NIST AI RMF requires continuous risk measurement and management: https://genai.owasp.org/llmrisk/llm01-prompt-injection/ and https://www.nist.gov/itl/ai-risk-management-framework

### Product rule

Python stays as BFF/control-plane glue and model adapter code where the current repo already uses it. Hot-path product infrastructure should be native-first:

- **Rust:** edge gateway, auth preflight, quota admission, semantic-cache admission plus C++ lookup invocation, rate limiting, payload limits, trace propagation, static-serving profile, low-latency proxy paths.
- **Go:** promotion controller, guardrail sidecar, background job runner, benchmark/load driver, webhook/event workers, SLO regression gates.
- **C++:** semantic cache, image metrics, policy/eval/stat tools, VTON preprocessing/evaluation kernels, deterministic CLIs used from CI and the API.
- **Python:** FastAPI BFF, real model adapters, repository abstraction, fallback orchestration, tests around product contracts.

### New production plan

1. **Console shell first.** Build `web/` with React/Vite/TypeScript, typed API client, dense enterprise shell, role-aware nav, degraded-mode banner, and `npm run build -> web/dist`. Serve it locally through FastAPI `StaticFiles`; keep production static serving as nginx or Rust edge profile.
2. **Thin vertical slice.** Ship one user-visible path end to end: browser LLM Playground -> Rust gateway -> FastAPI BFF -> real/fallback LLM -> DB request row -> feedback -> dashboard rollup -> Grafana/API metrics. Do not spread effort across every page before this works.
3. **VTON Studio slice.** Add person/garment upload, result compare, generated-output storage, MinIO/local object persistence, presigned download URL, metrics, feedback, and lineage drilldown.
4. **Operator control room.** Add Dashboard, Request History, Model Registry, Governance/Lineage, Audit Log, Champion/Challenger board, and Incident console. These pages should use existing DB/API contracts instead of mock data.
5. **Native enterprise boundary.** Push quota/session/rate/body/guardrail/static-edge responsibilities toward Rust; put async jobs/webhooks/reconcile/load gates in Go; keep C++ deterministic tools callable from Make/API/CI. Python should not become the production traffic choke point.
6. **Enterprise deployment profile.** Replace demo credentials with `.env.example` + secret loading, add Postgres migrations/pooling/backup/restore, TLS termination, Alertmanager, OpenTelemetry Collector, scanner/signing CI, dependency locks, and a product runbook.
7. **Cluster-grade serving option.** After local product readiness, add optional KServe/vLLM profile for LLM serving and keep deterministic fallback for offline demos.

### Build phases (each real, tested, `make`-runnable)

- [x] **P1 — Data layer.** DONE: `src/tryops/db.py` (SQLite, Postgres-compatible SQL) — requests/feedback/jobs/models/audit_log + dashboard rollup, 4 tests, `make db-init`.
- [x] **P2 — Product backend.** FastAPI exposes the product BFF routes for LLM, VTON, history, request detail, feedback, models, model promotion, lineage, dashboard rollups, native quota summaries, and online-experiment routing/analysis; real LLM/VTON paths keep deterministic fallbacks, product events persist to DB, and admin/read plus promotion scopes are tested.
- [~] **P3 — Frontend.** PARTIAL: React/Vite/TypeScript Console shell, left nav, typed API client, LLM Playground with direct/canary/A-B/bandit routing modes, VTON Studio contract form plus persisted side-by-side comparison outputs, Dashboard with native quota/showback read model, Request History, Pipeline Runs, Model Registry, Evaluation evidence plus optimization/Pareto/sustainability panel, Experiments board, Governance, Incident posture plus live bad-candidate and rollback drills, native incident workflow/postmortem evidence loading, Professor Demo mode, API-key session field, RBAC role-aware navigation, degraded banner, and responsive styling are implemented under `web/`; browser upload/download controls, full audit-log UI, live alert workflow controls, screenshots, and accessibility/export hardening remain.
- [x] **P4 — Services & edge wiring.** DONE: modular Rust gateway reverse-proxies `/api/*` to FastAPI `/v1/*`, adds request IDs, propagates trace context, enforces edge limits/preflight plus artifact-path preflight, calls the modular Go guardrail sidecar before LLM generation, and `docker-compose` ties gateway+api+db+prometheus+grafana+guardrail+minio+mlflow with healthchecks plus `make app-up`, `make app-smoke`, and `make app-down`.
- [~] **P5 — Monitoring & dashboard.** PARTIAL: API metrics, native Rust gateway metrics, native Go runtime telemetry for LLM tokens/sec plus live NVIDIA GPU memory/utilization/power, OpenTelemetry Collector wiring, native trace/log correlation, and Alertmanager page/ticket routing evidence now emit Prometheus/JSONL evidence; in-app dashboard timeseries, audit-log UI, external pager/chat credentials, and live OTLP exporters for full gateway->API->model trace stitching remain.
- [~] **P6 — Enterprise hardening.** PARTIAL: Rust edge API-key/JWT auth preflight, viewer/operator/admin RBAC session and nav enforcement, edge rate limits, native quota admission, optional file quota persistence, opt-in Postgres-backed distributed quota admission with fail-closed startup behavior, Postgres durable quota upsert mirroring, native Postgres migration/pooling evidence, native Postgres/MinIO backup-restore drill evidence, Valkey-compatible quota counter mirroring, `.env.example` plus Compose secret loading, native Go secret-rotation/workload-identity contract evidence, live Vault KV v2 secret retrieval/rotation evidence, Kubernetes Vault `SecretStore`/`ExternalSecret` manifests, native dependency-lock contract evidence across Python/Node/Rust/Go, native Rust TLS termination, payload limits, Rust->Go LLM guardrail enforcement, native C++ content-safety evidence, native Go full-stack load/SLO evidence, native Go incident workflow/postmortem evidence, GitHub Actions plus native Go CI/supply-chain contract, and local live Syft/Trivy/Cosign execution are in place; production Kubernetes External Secrets sync, external k6/locust confirmation, and external error-tracker DSN exercise remain.
- [~] **P7 — Demo & docs.** PARTIAL: `docs/presentation_outline.md` defines the professor demo path, the Console has a seeded Professor Demo view, `make professor-demo-acceptance` verifies the platform evidence bundle, and `make professor-demo-video` records a deterministic offline MP4 backup. Seed loader, product runbook, and full user/admin guides remain.
- [~] **P8 — Native-first product expansion.** PARTIAL: local P8 rows PA072-PA086 are now closed by verified native evidence. Rust gateway serves `web/dist` with SPA fallback, performs API-key/JWT auth preflight, terminates optional rustls HTTPS, makes native semantic-cache admission decisions plus optional C++ vector-cache lookups before FastAPI for LLM generation, mirrors accepted quota usage into Postgres plus Valkey-compatible counters with tenant usage snapshots, can use Postgres row locks as the shared quota admission ledger when `TRYOPS_GATEWAY_QUOTA_POSTGRES_ADMISSION=true`, degrades to the local quota ledger when a non-admission durable mirror is unavailable, emits a shared native trace/log envelope as JSONL, and has split container image definitions with Rust builder/runtime ABI compatibility checks for gateway/controller/guardrail/benchmark/C++ tools/API/web assets; native Go modules now cover VTON/LLM job execution, signed audit/webhook event dispatch, registry-webhook C++ policy enforcement, full-stack gateway/BFF load generation with SLO reporting, native CI/supply-chain contract validation plus live Syft/Trivy/Cosign evidence, native secret-rotation/workload-identity contract validation plus live Vault KV rotation, native incident workflow/postmortem evidence, distributed quota admission validation, SLO regression gating over native benchmark output, config-contract drift checks, TLS termination contract validation, Postgres migration/pool execution, Postgres/MinIO backup-restore drills, container-contract validation, trace-envelope validation/reporting, observability Collector/correlation validation, runtime telemetry export for LLM throughput/GPU memory, quota read-model/showback generation for the BFF dashboard, a CI-grade Rust/Go/C++ performance-budget report, GPTQ/AWQ model/runtime preflight, and vLLM OpenAI-compatible endpoint probing; Wave 3 native fabric now adds C++ admission control, retry budgets, PII/secret redaction, content-safety gating, tamper-evident audit logs, Bloom idempotency dedup, HyperLogLog cardinality, LRU/TTL response cache, cost attribution, reservoir/priority trace sampling, plus Go consistent-hash routing; native C++ also validates real GGUF artifacts for CPU-first LLM deployment preflight, validates trace envelopes, powers production A/B and guarded bandit routing through FastAPI/React, and feeds semantic-cache lookup plus VTON preprocessing/image-quality metrics through edge/API/job paths. External k6/locust confirmation, external error-tracker DSN exercise, live GPTQ/AWQ loading, live llama.cpp generation, live vLLM serving, production Kubernetes External Secrets sync, and live OTLP exporters remain.

### Acceptance (Gate: Product Ready)

A user opens the Console in a browser and can, with no terminal:

- Run a real or fallback LLM generation and see latency, token rate, VRAM/energy/cost when available, trace ID, quota usage, and feedback controls.
- Upload person+garment assets, run VTON, compare inputs/output, download through a persisted local/MinIO object URL, and inspect lineage.
- Review request history, request detail, feedback, dashboard rollups, model registry, governance/lineage, and audit log.
- As an admin/operator, promote or block a model through signed/policy-gated controls and see the action in metrics, audit, and incident views.
- Start the full local stack with `make app-up`; prove startup with `make app-smoke`; prove the native edge/job/SLO/config/container/CI/dependencies/performance/load/trace/observability/alerts/secrets/live-secrets/postgres/backup/TLS/quota-read-model/distributed-quota/runtime-telemetry/incident layer with `make native-rust-smoke`, `make native-edge-cache-smoke`, `make native-edge-guardrail-smoke`, `make native-admission-sample`, `make native-redaction-sample`, `make native-safety-sample`, `make native-audit-log-sample`, `make native-dedup-sample`, `make native-hll-sample`, `make native-consistent-hash-sample`, `make native-cache-sample`, `make native-cost-sample`, `make native-sampler-sample`, `make native-retry-sample`, `make native-quota-ledger-smoke`, `make native-distributed-quota-smoke`, `make native-quota-read-model-sample`, `make native-runtime-telemetry-sample`, `make native-observability-contract-sample`, `make native-alertmanager-contract-sample`, `make native-dependency-lock-contract-sample`, `make native-secret-rotation-contract-sample`, `make native-secret-rotation-live`, `make native-incident-workflow-sample`, `make native-db-migrator-sample`, `make native-backup-restore-sample`, `make native-tls-contract-sample`, `make native-tls-smoke`, `make native-static-smoke`, `make native-job-runner-sample`, `make vton-native-api-sample`, `make gateway-benchmark-native`, `make native-fullstack-load-sample`, `make native-ci-contract-live`, `make native-slo-gate-sample`, `make native-config-contract-sample`, `make native-container-contract-sample`, `make native-trace-envelope-sample`, and `make native-performance-budget-sample`; prove the native CPU-first LLM artifact path with `make llm-gguf-preflight-sample`; prove GPTQ/AWQ candidate/runtime readiness with `make llm-quantized-preflight-sample`; prove vLLM serving readiness or explicit skip status with `make llm-vllm-probe-sample`; prove the professor demo evidence with `make professor-demo-acceptance`; prove backend contracts with `PYTHONPATH=src python -m unittest discover -s tests`.
- Open the Console Professor Demo view and walk the seeded no-network/no-GPU path across quota, optimization, VTON quality, lineage, rollback, and governance without relying on live model service availability.

---

## Detailed TODO Checklist (long-term run, 86 items)

Granular, independently checkable items. IDs are stable (`PA###`). P1 is complete.

### P1 — Data layer (DONE)
- [x] PA001 SQLite schema: requests/feedback/jobs/models/audit_log + indexes
- [x] PA002 Repository API (insert/get/list for each entity)
- [x] PA003 `dashboard_summary()` rollup aggregate
- [x] PA004 `make db-init` target + default DB path
- [x] PA005 Data-layer unit tests (roundtrip, feedback, dashboard, audit, idempotent init)
- [~] PA006 Postgres driver path + parameterized DDL (enterprise profile). (`infra/postgres/migrations/` now contains native Postgres DDL for the product and quota tables, and `native/go/tryops-db-migrator/` applies it through pgxpool; the FastAPI repository still defaults to SQLite.)

### P2 — Product backend (FastAPI BFF + control plane)
- [x] PA007 `POST /api/llm/generate` — real LLM (R1/R2) + deterministic fallback, persist request row
- [x] PA008 `POST /api/vton/infer` — real diffusion VTON + fallback, persist + store image (MinIO/local)
- [x] PA009 `GET /api/history?kind=&limit=` — paginated request history from DB
- [x] PA010 `GET /api/request/{id}` — single request detail + lineage
- [x] PA011 `POST /api/feedback` — persist rating/label/comment + audit entry
- [x] PA012 `GET /api/dashboard` — live rollup for the in-app dashboard
- [x] PA013 `GET /api/models` — model registry served from DB
- [x] PA014 `POST /api/models/{id}/promote` — policy-gated promotion, writes audit + stage change
- [x] PA015 `GET /api/lineage/{id}` — full lineage (data/code/config/run/output hashes)
- [x] PA016 API-key auth middleware + admin scopes (reuse `auth.py`)
- [x] PA017 Request validation, payload-size limits, structured error envelope
- [x] PA018 Async VTON job endpoints (`POST /api/vton/jobs`, `GET /api/vton/jobs/{id}`) persisted
- [x] PA019 Backend integration tests via FastAPI `TestClient` (happy + auth + validation paths)
- [x] PA020 OpenAPI schema published + `/api/docs`
Evidence note: `tests/test_api_surface.py` verifies `/api/history`, `/api/request/{id}`, `/api/feedback`, `/api/dashboard`, `/api/models`, `/api/models/{id}/promote`, and `/api/lineage/{id}` are registered and auth-gated against an isolated SQLite DB.

### P3 — Frontend (React + Vite "TryOps Console")
- [x] PA021 Vite + React + TypeScript scaffold, router-like view state, app shell + left-nav. (`web/package.json`, `web/src/App.tsx`, `web/src/components/AppShell.tsx`; `npm run build` passes.)
- [x] PA022 Enterprise theme/design system (tokens, components). (`web/src/styles.css`, `MetricTile`, compact panel/table/form/button patterns.)
- [x] PA023 Typed API client layer (fetch wrappers, error handling). (`web/src/api.ts`, `web/src/types.ts`.)
- [x] PA024 LLM Playground: prompt box + variant selector (baseline/champion/challenger/candidate), quota plan, structured/shadow/cache toggles.
- [~] PA025 Live metrics panel beside each LLM response. (Latency, tokens/sec, memory, quota, trace/request ID, and cost contract render from API response; true VRAM/energy require live exporters.)
- [~] PA026 VTON Studio: person + garment asset path controls and local preview. (Real browser upload endpoint is still missing; current API contract uses local file paths.)
- [~] PA027 VTON result side-by-side (input vs try-on) + download + metrics. (`/api/vton/comparison` serves generated comparison metadata, `/api/artifacts/file` serves persisted PNG/JSON artifacts behind API-key auth and Rust gateway path preflight, and the Console renders person/garment plus baseline/candidate outputs with metrics/failure labels; explicit download controls and MinIO presigned URLs remain.)
- [x] PA028 Feedback widget wired to `POST /api/feedback`
- [~] PA029 Dashboard page: live tiles from `/api/dashboard`. (Tiles and recent table are live; timeseries charting remains.)
- [x] PA030 Model Registry viewer (stage, signed, approved, metrics)
- [~] PA031 Governance / Lineage viewer. (Lookup view calls `/api/lineage/{id}`; richer click-through provenance graph remains.)
- [~] PA032 Champion/Challenger release board. (Stage lanes render; explicit "block a bad model" action remains.)
- [~] PA033 Incident console. (Incident posture/drill rows render, the "Block bad model" action runs a seeded failing candidate through `/api/promotion/evaluate`, the rollback drill loads deployment rollback state behind the Rust gateway, and the Console loads `tryops.native_incident_workflow.v1` plus the generated postmortem path through `/api/incidents/workflow`; live Alertmanager-trigger controls remain.)
- [x] PA034 Request history page (filter by kind, drill-ready table) plus Pipeline Runs view over run-context/OpenLineage/lineage evidence.
- [~] PA035 Auth/login (API key) + session + role-aware nav. (API-key field persists in browser storage; `/api/auth/session` returns the active RBAC principal and allowed Console navigation; the React shell hides views outside the active scopes. Formal OIDC/login UX remains production hardening.)
- [x] PA036 Degraded-mode banner (API unavailable -> degraded state)
- [x] PA037 Build -> `web/dist`, served by Rust gateway static SPA fallback at `/`. (FastAPI `StaticFiles` remains optional; `make native-static-smoke` proves `/` and SPA fallback.)
- [~] PA038 Responsive layout + accessibility (keyboard, contrast, aria) + screenshot/export. (Responsive CSS, labels, aria-hidden icons, and keyboard-native controls exist; screenshot/export pass remains.)

### P4 — Services & edge wiring
- [x] PA039 Rust gateway reverse-proxy to FastAPI (forward + preflight + add request-id). (13 Rust files under `native/rust/tryops-gateway/src/`; `/api/*` maps to `/v1/*`; `make native-rust-smoke` proves `/api/health` proxying plus `traceparent` response propagation.)
- [x] PA040 Gateway rate-limit + payload limit + signed-artifact preflight on admin routes. (Native per-key minute limiter, `RequestBodyLimitLayer`, and `x-tryops-artifact-signed` gate for promotion/model-admin paths.)
- [x] PA041 `docker-compose`: gateway + api + db(postgres) + prometheus + grafana + guardrail + minio. (`docker-compose.yml` plus `Dockerfile.gateway`; `docker compose config` validates.)
- [x] PA042 Healthchecks + `depends_on` ordering + restart policy. (API healthcheck, gateway compiled `health-check` mode, gateway waits for healthy API, restart policies on stack services.)
- [x] PA043 `make app-up` / `make app-smoke` / `make app-down` (one-command stack plus native Go full-stack readiness probe and native Go job-runner proof. `make app-smoke` uses the disposable Compose project `tryops_app_smoke`, recreates volumes before the run, tears them down on exit, and verifies evaluation-summary, optimization-panel, native edge-auth rejection, pipeline-run ledger, LLM/VTON job execution, bad-candidate promotion-gate, rollback-state artifact coverage, and MLflow health through the Rust gateway.)
- [x] PA044 `.env` config + secrets (no hardcoded creds). (`.env.example` documents required local secret variables, `.env` remains ignored, `docker-compose.yml` now uses Compose secrets for Postgres/MinIO/MLflow/gateway quota DSN paths, the Rust gateway reads `TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN_FILE`, and `native/go/tryops-config-contract/` validates 4 secrets, direct credential-env absence, and `.env.example` coverage via `make native-config-contract-sample`.)
- [~] PA045 MinIO bucket for generated images + presigned URL serving. (Local persisted artifact serving works through `/api/artifacts/file`; MinIO bucket creation and presigned URL handoff remain.)
- [x] PA046 Static-asset serving profile: Rust gateway serves `web/dist` for production compose; Vite build remains local/dev source. (`Dockerfile.gateway`, `TRYOPS_GATEWAY_STATIC_DIR`, `make native-static-smoke`.)

### P5 — Monitoring & dashboard
- [~] PA047 App Prometheus metrics: request_total, latency histogram, energy, by-model labels. (FastAPI exposes request/latency/trace/cache metrics by model alias; Rust gateway now exposes native request counters, latency histogram buckets, quota decisions, rate-limit events, upstream errors, and in-flight gauge. Full live energy-by-model exporters remain.)
- [x] PA048 Prometheus scrape config for api + gateway. (`infra/prometheus/prometheus.yml` scrapes `api:8080`, `gateway:8081`, and `guardrail:18083`.)
- [x] PA049 Grafana dashboards bound to live API/gateway metrics. (`tryops-service-overview` now includes Gateway Request Rate, Gateway p95 Latency, and Gateway Rejections and Upstream Errors panels.)
- [ ] PA050 In-app dashboard timeseries charts (from DB rollups + Prometheus)
- [~] PA051 OpenTelemetry Collector traces spanning gateway -> API -> model call. (`infra/otel/collector.yml` now defines OTLP gRPC/HTTP, JSONL filelog, batch/resource/memory processors, file exporters, and health extension; `docker-compose.yml` runs `otel-collector`; Prometheus scrapes `otel-collector:8888`; `native/go/tryops-observability-contract/` validates 3 Collector pipelines and gateway/API trace correlation. Live OTLP export from every runtime under load remains.)
- [~] PA052 Structured request logging (JSONL + DB), correlation by trace-id. (FastAPI structured logs embed native envelopes; the Rust gateway now writes `tryops.native_trace_log_envelope.v1` JSONL when `TRYOPS_GATEWAY_STRUCTURED_LOG_PATH` is set; `make native-observability-contract-sample` proves gateway logs, API spans, API logs, shared trace IDs, service names, model-call metadata, and payload redaction. DB-backed log search remains.)
- [x] PA053 Alert rules (latency regression, error budget burn) + Alertmanager. (`infra/alertmanager/alertmanager.yml` routes page/ticket severities, Prometheus now forwards alerts to `alertmanager:9093`, `docker-compose.yml` runs Alertmanager with healthcheck/storage, the Go controller accepts `/alerts/webhook` Alertmanager payloads, and `native/go/tryops-alertmanager-contract/` validates 16 alert rules, receivers, inhibition, Compose wiring, and Prometheus alertmanager targets via `make native-alertmanager-contract-sample`.)
- [ ] PA054 Audit-log UI view (who promoted/approved/rolled back what, when)

### P6 — Enterprise hardening
- [x] PA055 RBAC roles: viewer / operator / admin enforced on routes + nav. (`configs/api_keys.json` now has active viewer/operator/admin demo principals with `session:read`; FastAPI exposes `/api/auth/session` and `/v1/auth/session`; the Rust gateway protects `/v1/auth/session` before proxying; the Console filters nav by the returned permission set and promotion actions use the active session key instead of a hard-coded privileged key. Verified with `PYTHONPATH=src python -m unittest tests.test_auth tests.test_api_surface`, `cargo test --manifest-path native/rust/tryops-gateway/Cargo.toml auth`, and `npm run typecheck`.)
- [x] PA056 Rate limiting + per-tenant quota enforcement. (Rust gateway enforces per-tenant edge rate limits and native quota decisions; Python delegates quota to `TRYOPS_QUOTA_GATEWAY_URL` when present. `TRYOPS_GATEWAY_QUOTA_POSTGRES_ADMISSION=true` makes Postgres the shared admission ledger using transactional row locks, and `make native-distributed-quota-smoke` proves two gateway instances admit exactly 20/32 concurrent free-plan LLM requests with 12 global rejections and zero oversell.)
- [x] PA057 LLM guardrails at the edge. (`TRYOPS_GATEWAY_GUARDRAIL_URL` makes the Rust gateway call the native Go guardrail sidecar before proxying `/api/llm/generate`; `make native-edge-guardrail-smoke` proves prompt-injection/system-prompt leakage is blocked with HTTP 403 and `tryops_gateway_guardrail_decisions_total` metrics.)
- [x] PA058 Postgres profile + migration runner + connection pooling. (`infra/postgres/migrations/` carries idempotent product/quota SQL, `native/go/tryops-db-migrator/` uses `github.com/jackc/pgx/v5/pgxpool`, `make native-db-migrator-sample` emits plan-mode CI evidence with 20/20 checks, and live apply against Compose Postgres wrote `artifacts/eval/postgres/native_postgres_migration_live.json` with 33/33 checks, pooled ping/acquire, two applied migrations, idempotent re-run, and live table verification.)
- [x] PA059 DB backup/restore scripts + scheduled restore drill. (`native/go/tryops-backup-restore/` validates Compose storage, `infra/backup/restore_drill.cron`, restore isolation, and required tooling; `make native-backup-restore-sample` emits 20/20 plan checks; live drill with `TRYOPS_POSTGRES_BACKUP_DSN=... make native-backup-restore-live` wrote `artifacts/eval/backup/native_backup_restore_live.json` with 50/50 checks, a 42,609-byte Postgres custom dump restored into `tryops_restore_drill`, seven table row-count matches, MinIO `mc mirror` backup/restore of one object into `tryops-restore-drill`, and cleanup of temporary restore targets.)
- [~] PA060 Secrets management (vault/workload identity), key rotation. (`configs/secret_rotation_policy.json` declares Vault KV paths, owners, rotation windows, hash-only API-key rotation, and SPIFFE-ready workload identity; `infra/kubernetes/secret-management/` adds a Vault `SecretStore`, `ExternalSecret`, non-automounted `tryops-runtime` ServiceAccount, and projected service-account token for the gateway; `native/go/tryops-secret-rotation-contract/` validates the plan with parsed JSON/YAML and can exercise live Vault KV v2 write/read/rotation through `make native-secret-rotation-live`. Latest local live evidence passes 65/65 checks with 8 managed secrets, 5 live KV paths, 8 rotated secret properties, Vault 1.19.5 health, token-file auth, versioning 1->2, no raw secret emission, and `production_ready=true`; production Kubernetes External Secrets controller sync remains.)
- [x] PA061 TLS/HTTPS termination config for the production profile. (The Rust gateway reads `TRYOPS_GATEWAY_TLS_CERT_PATH`/`TRYOPS_GATEWAY_TLS_KEY_PATH` and serves HTTPS through axum-server/rustls; `docker-compose.yml` adds optional `gateway-tls` profile with `TRYOPS_TLS_CERT_PEM`/`TRYOPS_TLS_KEY_PEM` Compose secrets; `native/go/tryops-tls-contract/` validates the profile. `make native-tls-contract-sample` emits 24/24 plan checks, and `make native-tls-smoke` emits 30/30 live checks with TLS1.3, HTTPS `/health` 200, and plaintext HTTP rejection.)
- [x] PA062 `make ci`: lint + tests + build images + SBOM + Trivy scan + Cosign sign. (`.github/workflows/ci.yml` defines Python/Node/Go/Rust/C++ tests, Compose validation, native contract evidence, seven-image Docker Buildx matrix, Syft SPDX SBOM generation, Trivy HIGH/CRITICAL image scan gate, artifact upload, and Cosign keyless signing on non-PR pushes. `make ci` now mirrors the local live evidence path through `make native-ci-contract-live`; `native/go/tryops-live-supply-chain/` executes pinned Syft/Trivy/Cosign containers and emits `artifacts/eval/ci/live_supply_chain_report.json` with 613 Syft packages, 0 HIGH/CRITICAL Trivy findings, and verified Cosign SBOM signature evidence. `native/go/tryops-ci-contract/` now emits `artifacts/eval/ci/native_ci_contract.json` with 17/17 checks, `missing_tools=[]`, and `production_ready=true`.)
- [x] PA063 Dependency lockfile (fix the accelerate/bitsandbytes drift caught in the benchmark run). (`uv.lock` now pins the Python project resolution including `accelerate=1.14.0`, `bitsandbytes=0.49.2`, `torch=2.11.0`, `transformers=5.11.0`, and `vllm=0.22.1`; `web/package-lock.json`, Rust `Cargo.lock`, and Go `go.sum` files cover the other runtimes. `native/go/tryops-dependency-lock-contract/` validates all four ecosystems and emits `artifacts/eval/dependencies/native_dependency_lock_contract.json`; latest local evidence passes 89/89 checks with 326 Python packages, 59 Node packages, 228 Rust crates, and 32 Go modules.)
- [~] PA064 Full-stack load test (native Go driver plus k6/locust confirmation) with SLOs + report. (`native/go/tryops-fullstack-load/` starts FastAPI plus the Rust gateway, drives six weighted product scenarios through `/api/*`, applies per-scenario SLOs, records k6/locust availability, and emits `artifacts/eval/load/native_fullstack_load.json`; latest local run passed 6/6 scenarios with 504 requests, zero errors, worst p95 39.965 ms, and `external_ready=false` because neither `k6` nor `locust` is installed.)
- [~] PA065 Error tracking + incident workflow + postmortem template. (`native/go/tryops-incident-workflow/` emits `artifacts/eval/incidents/native_incident_workflow.json` with OTel-shaped local error event fields, Alertmanager payload validation, controller/event-dispatcher checks, rollback linkage, a 5-step detected->triaged->mitigated->postmortem_drafted->resolved timeline, and `docs/incident_postmortem_template.md` rendering to `artifacts/eval/incidents/postmortem_bad_candidate.md`. Latest local evidence passes 8/8 checks; `production_ready=false` until `GLITCHTIP_DSN`, `TRYOPS_ERROR_TRACKING_DSN`, or `SENTRY_DSN` is configured and exercised.)

### P7 — Demo & documentation
- [ ] PA066 Seed/demo data loader (sample requests, models, feedback)
- [ ] PA067 Product runbook (`docs/product_runbook.md`): deploy, operate, recover
- [x] PA068 3-minute product demo script (end-user + admin paths). (`docs/presentation_outline.md` and `web/src/components/ProfessorDemoView.tsx` define the browser path; `make professor-demo-acceptance` verifies the platform evidence bundle.)
- [x] PA069 Screenshots / recorded walkthrough of the Console. (`make professor-demo-video` renders 9 PNG frames and `artifacts/demo/professor_demo_video/professor_demo_backup.mp4` from the shared Console storyboard; `artifacts/eval/demo_video/professor_demo_video.json` records the video hash, dimensions, duration, and checks.)
- [ ] PA070 End-user guide + admin guide
- [x] PA071 Backup offline demo path (degraded mode, seeded artifacts). (`web/src/components/ProfessorDemoView.tsx` exposes the no-network/no-GPU seeded path; `make professor-demo-acceptance` validates seeded local artifacts, native quota evidence, and the live bad-candidate policy gate.)

### P8 — Native-first product expansion
- [x] PA072 Rust static-file/SPA fallback profile for `web/dist` behind the same edge binary. (`native/rust/tryops-gateway/src/static_assets.rs`; `/api/*` remains proxied.)
- [x] PA073 Rust session/auth preflight module for API-key/JWT validation before FastAPI. (`native/rust/tryops-gateway/src/auth.rs` loads the hashed API-key registry, verifies scoped API keys from query/header/body, supports optional HS256 bearer JWTs via `TRYOPS_GATEWAY_JWT_HS256_SECRET`, forwards principal metadata, exports auth-decision metrics, and `make app-smoke` proves missing-key 401 plus missing-scope 403 at the gateway.)
- [x] PA074 Rust Valkey/Postgres quota-ledger adapter with tenant usage snapshots. (`native/rust/tryops-gateway/src/quota_durable.rs` initializes/upserts `tryops_quota_usage` when `TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN` is set, mirrors accepted increments to Valkey-compatible RESP `INCRBY`/`EXPIRE` counters when `TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR` is set, degrades to the local quota ledger if a requested durable mirror is unavailable at startup, and `quota_snapshot.rs` adds per-period hashed-tenant aggregates to native quota snapshots; docker compose wires Postgres plus Valkey for the gateway.)
- [x] PA075 Rust edge cache admission hook for semantic-cache hits/misses before API proxy. (`native/rust/tryops-gateway/src/semantic_cache.rs` parses LLM requests at the edge, honors `semantic_cache_enabled`, skips sensitive prompts, hashes admitted cache keys, optionally invokes `artifacts/native/tryops_semantic_cache_cli` for C++ vector lookup from seeded/native entries, forwards `x-tryops-edge-cache-*` headers to FastAPI, exports `tryops_gateway_semantic_cache_admissions_total` plus `tryops_gateway_semantic_cache_lookups_total`, and `make native-edge-cache-smoke` proves admitted, sensitive-skip, and native C++ hit decisions without Python.)
- [x] PA076 Go background job runner for VTON/LLM jobs with context deadlines and retry policy. (`native/go/tryops-job-runner/` is split into config, payload, HTTP, retry, runner, response-summary, report, asset, and test modules; `make native-job-runner-test` covers retry/poll/deadline behavior; `make native-job-runner-sample` writes `artifacts/eval/jobs/native_job_runner_report.json`; `make app-smoke` runs it against the Rust gateway.)
- [x] PA077 Go audit/webhook dispatcher for promotion, feedback, incident, and quota events. (`native/go/tryops-event-dispatcher/` validates CloudEvents-style event envelopes, writes `tryops.native_audit_event.v1` JSONL audit records, signs webhook payloads with HMAC-SHA256, retries delivery, and emits `artifacts/eval/events/native_event_dispatcher_report.json`; `make native-event-dispatcher-test` and `make native-event-dispatcher-sample` pass.)
- [x] PA078 Go SLO regression gate that consumes native benchmark output and fails CI on regressions. (`native/go/tryops-slo-gate/` consumes `tryops.native_gateway_benchmark.v1`, applies latency/error/throughput/ratio rules, exits nonzero on regression, and emits `artifacts/eval/slo/native_slo_gate_report.json`; `make native-slo-gate-test` and `make native-slo-gate-sample` pass.)
- [x] PA079 C++ VTON preprocessing service/CLI wired into API job execution. (`/v1/vton/infer` now returns `native_vton.preprocessing` derived from `artifacts/native/tryops_vton_preprocess_cli`, async VTON jobs inherit the same runner/result path, sidecar reports persist `native_execution`, and `make vton-native-api-sample` proves native person+garment preprocessing availability through the API.)
- [x] PA080 C++ policy/eval library wired into Go promotion controller decisions. (`native/go/tryops-controller/` now has split native-policy candidate parsing, C++ wire-format rendering, CLI execution, and webhook gate modules; signed registry webhooks carry `policy_candidate`, `TRYOPS_CONTROLLER_POLICY_CLI` makes the Go controller re-run `artifacts/native/tryops_policy_cli`, and `make registry-webhook-sample`, `make native-go-test`, plus `make native-cpp-test` pass.)
- [x] PA081 C++ image quality metrics exported to dashboard request details. (`src/tryops/vton_native_bridge.py` invokes `artifacts/native/tryops_image_metrics_cli` on the API output, stores `native_quality_score` in the VTON report, persists it to the request `quality` column for request details/dashboard rollups, and `artifacts/eval/vton_native_api/vton_native_api_report.json` proves quality persistence.)
- [x] PA082 Native trace/log envelope shared by Rust, Go, C++, and FastAPI. (`contracts/native_trace_log_envelope.schema.json` defines the W3C/OTel-backed contract; `src/tryops/trace_envelope.py` adds FastAPI envelopes to structured logs; `native/rust/tryops-gateway/src/trace_envelope.rs` constructs gateway envelopes; `native/cpp/tryops_trace_envelope/` validates the contract in C++; `native/go/tryops-trace-envelope/` validates all four runtimes and emits `artifacts/eval/trace_envelope/native_trace_envelope_report.json`; `make native-trace-envelope-sample` passes with 4/4 envelopes.)
- [x] PA083 Native config contract tests to prevent env var drift across services. (`native/go/tryops-config-contract/` parses `docker-compose.yml` with `gopkg.in/yaml.v3`, checks required enterprise services, env vars, Compose secrets, direct credential-env absence, `.env.example`, port interpolations, healthchecks, dependency conditions, named volumes, and Rust gateway env references, and emits `artifacts/eval/config/native_config_contract_report.json`; `make native-config-contract-test` and `make native-config-contract-sample` pass. The native Postgres migrator is separately covered by `make native-db-migrator-sample`.)
- [x] PA084 Container image split: gateway, controller, guardrail, benchmark, C++ tools, API, web assets. (`Dockerfile.controller`, `Dockerfile.benchmark`, `Dockerfile.cpp-tools`, and `Dockerfile.web-assets` join the existing API/gateway/guardrail images; `docker-compose.yml` now has optional `ops`, `tooling`, and `assets` profiles; `configs/container_images.json` declares the seven-image contract; `native/go/tryops-container-contract/` validates Dockerfiles, source paths, Compose build wiring, multi-stage native builds, non-SDK runtime stages, and Rust builder/runtime ABI-suite compatibility; `make native-container-contract-sample` emits `artifacts/eval/containers/native_container_contract_report.json` with 89/89 checks passing.)
- [x] PA085 Native performance budget report generated in CI from Rust/Go/C++ test artifacts. (`native/go/tryops-performance-budget/` is split into config, typed artifact loading, budget evaluation, Markdown, report, and tests; it consumes native gateway benchmark, native SLO gate, C++ perf stats, config-contract, and native binary evidence, emits `artifacts/eval/performance/native_performance_budget.json` plus Markdown, and `make native-performance-budget-test` / `make native-performance-budget-sample` pass.)
- [x] PA086 Replace Python-only quota/accounting path with native-first quota ledger and BFF read model. (`native/go/tryops-quota-read-model/` transforms Rust gateway quota snapshots into `tryops.native_quota_read_model.v1` tenant utilization/showback evidence; `/api/quota/summary` serves it through the BFF with scoped admin-read auth and runtime fallback; the Console Dashboard renders tenant risk, used units, showback, and native-source status; `make native-quota-read-model-sample`, `make native-go-test`, `make native-evaluation-index-test`, and `npm run typecheck` pass.)

### Suggested execution order

1. P3 Console shell: PA021-PA023, PA035-PA038.
2. Thin LLM slice: PA024-PA025, PA028-PA029, PA050-PA052.
3. VTON product slice: PA026-PA027, PA045, PA079, PA081.
4. Operator views: PA030-PA034, PA054, PA066-PA070.
5. Native-first enterprise boundary: PA072-PA086 is closed locally; keep live/distributed followups under the production-profile items below and the long-term backlog.
6. Production profile remaining: PA060 production Kubernetes External Secrets controller sync, PA064 external confirmation, and PA065 external error-tracker DSN exercise.

Ship the thin vertical slice first: UI -> Rust gateway -> API -> real/fallback LLM -> DB -> feedback -> dashboard -> Grafana. Breadth is secondary until this loop is smooth.

---

## Long-Term / Scale Backlog (72 more items, PA072–PA143)

Advanced enterprise dimensions beyond the MVP product. Not blocking the first vertical slice; sequence after the P2–P7 core ships.

### Scalability & performance (PA072–PA081)
- [ ] PA072 Horizontal scaling: stateless API replicas behind the gateway/load balancer
- [ ] PA073 Redis response cache + cache-invalidation strategy
- [ ] PA074 Embedding-based semantic cache for LLM (Theme Q) with hit-rate metering
- [ ] PA075 Async task queue (Celery/RQ) backing VTON jobs (replace in-memory queue)
- [ ] PA076 Model warm-pool / preloading to remove cold-start latency
- [ ] PA077 Batch inference endpoint (multi-prompt / multi-image)
- [ ] PA078 DB connection pooling + read replicas (Postgres)
- [ ] PA079 CDN for static assets + generated images
- [ ] PA080 Streaming responses (SSE) for LLM token-by-token in the UI
- [ ] PA081 Autoscaling policy (HPA) on queue depth / GPU utilization

### Multi-tenancy & accounts (PA082–PA089)
- [ ] PA082 Organizations / workspaces model + data isolation
- [ ] PA083 User management CRUD (invite, deactivate, roles)
- [ ] PA084 Team roles & invitations flow
- [ ] PA085 Per-tenant quota + rate limits
- [ ] PA086 Usage metering per tenant/user/model
- [ ] PA087 Billing/subscription tiers (plans, limits)
- [ ] PA088 Invoicing / cost export per tenant
- [ ] PA089 Tenant-scoped audit log + data export

### ML lifecycle deepening (PA090–PA099)
- [ ] PA090 Live MLflow tracking wired to the promotion pipeline
- [ ] PA091 DVC dataset versioning + MinIO push, surfaced in UI
- [ ] PA092 Trigger evaluation/leaderboard runs from the UI
- [x] PA093 A/B test + multi-armed-bandit routing in production (Theme T). (`/api/llm/generate` now accepts `experiment_ab` and `experiment_bandit` routing modes that call the native C++ `tryops_experiment_router` when built; `/api/experiments/route`, `/api/experiments/analyze`, and `/api/experiments/summary` expose guarded route decisions plus sequential-test evidence; the React Console adds an Experiments board and the LLM Playground can exercise the production experiment path.)
- [ ] PA094 Canary / shadow deploy controllable from the Console
- [ ] PA095 Auto model-card publish to the registry viewer
- [ ] PA096 Dataset upload + validation (Great Expectations) in UI
- [ ] PA097 Drift monitor surfaced in UI with alerts + re-eval trigger
- [ ] PA098 Feedback-to-retraining loop (collect → label → re-evaluate)
- [ ] PA099 Champion/challenger auto-promotion workflow with gates

### Security & compliance (PA100–PA109)
- [ ] PA100 OIDC / SSO login (Keycloak) replacing API-key-only
- [ ] PA101 Fine-grained RBAC permissions (per-resource, per-action)
- [ ] PA102 Tamper-evident / append-only audit log (hash chain)
- [ ] PA103 GDPR data retention + right-to-deletion workflows
- [ ] PA104 PII detection + redaction enforced at ingress/egress (Presidio)
- [ ] PA105 Output content moderation / safety classifier (Llama Guard)
- [ ] PA106 Secrets rotation automation + vault integration
- [ ] PA107 Consent / Terms-of-Service acceptance flow
- [ ] PA108 Recurring vulnerability + dependency scanning in CI (Trivy/Grype)
- [ ] PA109 Periodic security review / pen-test checklist

### Reliability / SRE (PA110–PA117)
- [ ] PA110 SLOs + error budgets per service with burn-rate alerts (Theme R)
- [ ] PA111 Scheduled chaos drills (GPU OOM, slow decode, poisoned candidate)
- [ ] PA112 Automated rollback on burn-rate breach
- [ ] PA113 Blue/green or canary deploy with health gates
- [ ] PA114 Zero-downtime DB migrations
- [ ] PA115 Backup/restore drills + RPO/RTO targets
- [ ] PA116 On-call runbooks + paging integration (PagerDuty/Opsgenie)
- [ ] PA117 Multi-AZ / HA topology (stretch)

### Product / UX depth (PA118–PA127)
- [ ] PA118 First-run onboarding + guided tour
- [ ] PA119 In-app notifications + activity feed
- [ ] PA120 Export / share results (link, PNG, JSON)
- [ ] PA121 Self-service API-key management UI
- [ ] PA122 Per-user usage dashboard
- [ ] PA123 Dark mode + theming
- [ ] PA124 i18n / localization
- [ ] PA125 Mobile-responsive / PWA
- [ ] PA126 Keyboard shortcuts + command palette
- [ ] PA127 In-app help / contextual docs

### Integrations & extensibility (PA128–PA135)
- [ ] PA128 Versioned public REST API (v1/v2) + deprecation policy
- [ ] PA129 Official client SDKs (Python + JS/TS)
- [ ] PA130 Webhooks for events (promotion, drift, incident)
- [ ] PA131 Slack / email notification channels
- [ ] PA132 MCP server exposing TryOps tools to agents
- [ ] PA133 Third-party model-provider adapters (OpenAI-compatible, vLLM, Bedrock)
- [ ] PA134 Bulk import/export of datasets and results
- [ ] PA135 Plugin / extension hook system

### Data & analytics (PA136–PA143)
- [ ] PA136 Analytics events pipeline (request/usage telemetry)
- [ ] PA137 Usage-analytics dashboard (volume, latency, cost trends)
- [ ] PA138 Cohort / retention analysis
- [ ] PA139 Cost analytics per tenant/model/workload
- [ ] PA140 Feedback analytics feeding the eval loop
- [ ] PA141 Full-text search over request history
- [ ] PA142 Data-warehouse export (Parquet/BigQuery)
- [ ] PA143 Embedded BI dashboard for admins

## Wave 3 — Resilience, Trust & Edge Fabric (native-first)

> Design principle: every item below pushes a control-plane or data-plane concern
> down to a **low-level engine** (C++/Go/Rust) at the production boundary, with a
> thin Python bridge and graceful offline fallback. Python orchestrates; native
> decides on the hot path. Each item must ship a real binary + test + measured
> sample, not a checkbox.

### Resilience & admission control (PA144–PA153)
- [x] PA144 Native adaptive admission controller — token bucket + circuit breaker + load shedding (C++) — `native/cpp/tryops_admission`, `make native-admission-{build,sample,test}`, wired into `ci`+`smoke`; sample sheds 50% of a 414-event mixed-traffic stream, native binary agrees bit-for-bit with the Python reference
- [x] PA145 Native circuit breaker with half-open probing — closed→open on windowed error-rate ≥ threshold, open→half-open after cooldown, half-open→closed on healthy probe (sample: 2 trips, 1 recovery, ends closed)
- [x] PA146 Native concurrency limiter / bulkhead isolation — in-flight slot accounting with duration-based release (`max_concurrency` gate, `peak_inflight` reported)
- [x] PA147 Native retry budget + exponential backoff with jitter — `native/cpp/tryops_retry`, `make native-retry-{build,sample,test}`, wired into `ci`+`smoke`; full/equal/none jitter, cumulative retry budget (gRPC-style storm prevention), shared xorshift64 so native == reference incl. jittered backoff sum; sample: 71.2%→89.3% success, 206 retries denied by budget
- [ ] PA148 Native request hedging (tail-latency cut)
- [ ] PA149 Deadline propagation + timeout enforcement at boundary
- [ ] PA150 Graceful shutdown / connection draining in Rust gateway
- [ ] PA151 Backpressure signalling end-to-end (gateway→controller)
- [ ] PA152 Priority queueing / weighted fair share across tenants
- [ ] PA153 Brownout mode (shed non-critical features under load)

### Trust & tamper-evidence (PA154–PA162)
- [x] PA154 Native Merkle tamper-evident audit log (C++) — `native/cpp/tryops_audit_log`, `make native-audit-log-{build,sample,test}`, wired into `ci`+`smoke`; hand-rolled SHA-256 verified bit-for-bit against Python `hashlib` (incl. FIPS-180-4 KAT vectors); sample tamper-detection confirmed
- [x] PA155 Append-only hash-chained event ledger + verification — each entry chains `sha256(prev_chain + leaf)`; `verify_chain()` recomputes and detects any in-place mutation
- [~] PA156 Signed audit checkpoints + inclusion proofs — O(log n) Merkle inclusion proofs implemented + verified (`prove`/`verify_inclusion`); HMAC checkpoint signing still TODO
- [x] PA157 Native PII/secret redaction engine (C++ scrubber) — `native/cpp/tryops_redaction`, `make native-redaction-{build,sample,test}`, wired into `ci`+`smoke`; 10 detectors (email, CC w/ Luhn gate, API/AWS/GitHub keys, bearer, JWT, IPv4, SSN, phone) + FNV-1a audit fingerprints; native C++ and Python reference agree bit-for-bit incl. fingerprints
- [x] PA158 Content-safety gate (prompt-injection + toxicity) at boundary — `native/cpp/tryops_safety`, `make native-safety-{build,sample,test}`, wired into `ci`+`smoke` and FastAPI ingress guardrails; sample labels pass at 100% accuracy with zero native/reference disagreement, and `/v1/llm/generate` verdicts include `native_engine.content_safety`
- [x] PA159 Native idempotency-key dedup (bloom filter, C++) — `native/cpp/tryops_dedup`, `make native-dedup-{build,sample,test}`, wired into `ci`+`smoke`; optimal m/k sizing from (n, p), Kirsch-Mitzenmacher double hashing, zero false negatives; sample: 600 reqs → 400 unique admitted / 200 replays rejected, native == reference bit-for-bit
- [ ] PA160 Request/response signing (HMAC) at the boundary
- [ ] PA161 SLSA build-provenance attestation verification
- [ ] PA162 Data-access audit + least-privilege enforcement

### Edge & performance fabric (PA163–PA172)
- [x] PA163 Native consistent-hash ring for sharding/routing (Go) — `native/go/tryops-consistent-hash`, `make native-consistent-hash-{build,test,sample}`, wired into `native-go-test`+`ci`+`smoke`; 200 virtual nodes + fmix64-finalised FNV hashing → imbalance 1.14; node removal remaps only 18.4% of keys (≈ ideal 1/N) and only that node's keys
- [x] PA164 Native HyperLogLog cardinality estimator for metrics (C++) — `native/cpp/tryops_hll`, `make native-hll-{build,sample,test}`, wired into `ci`+`smoke`; FNV-1a+fmix64 hash, HLL++ linear-counting small-range correction; sample: 8000 distinct from 24k observations estimated at 8020 (0.26% error, 16KB state), native == reference
- [x] PA165 Native reservoir/priority trace sampler (C++) — `native/cpp/tryops_sampler`, `make native-sampler-{build,sample,test}`, wired into `ci`+`smoke`; Algorithm-R reservoir + priority (force-keep error/slow spans) modes, shared deterministic xorshift64 so native == reference bit-for-bit incl. randomized picks; uniformity test passes
- [x] PA166 Native response cache with TTL + LRU eviction (C++) — `native/cpp/tryops_cache`, `make native-cache-{build,sample,test}`, wired into `ci`+`smoke`; LRU + sliding-TTL, O(1) hash+list; Zipfian sample: 77.6% hit rate (256-cap over 800 keys), 866 evictions, native == reference bit-for-bit
- [ ] PA167 Native streaming token relay (SSE) at gateway
- [ ] PA168 Native zstd/gzip response compression at edge
- [ ] PA169 Connection-pool + keep-alive tuning (measured)
- [ ] PA170 Edge request coalescing (single-flight) for hot keys
- [ ] PA171 Structured JSON access log + adaptive sampling
- [ ] PA172 Latency-aware load balancing (EWMA power-of-two-choices) in Go

### Multi-tenancy & quota (PA173–PA180)
- [ ] PA173 Tenant isolation namespaces + per-tenant config
- [ ] PA174 Hierarchical quota (org→team→user) read model
- [ ] PA175 Per-tenant rate limits + burst credits
- [ ] PA176 Tenant-scoped envelope encryption keys
- [ ] PA177 Noisy-neighbour detection + auto-throttle
- [ ] PA178 Tenant offboarding + GDPR data-erasure
- [ ] PA179 Usage metering → billing export (per tenant)
- [ ] PA180 Tenant-level SLA tracking + breach alerts

### Privacy, governance & FinOps (PA181–PA189)
- [ ] PA181 Native data-residency policy enforcement
- [ ] PA182 Differential-privacy noise for aggregate analytics
- [ ] PA183 Consent + data-retention lifecycle engine
- [x] PA184 Native cost-attribution engine (token/GPU-sec → $) — `native/cpp/tryops_cost`, `make native-cost-{build,sample,test}`, wired into `ci`+`smoke`; per-tenant/per-model showback of token+GPU+energy cost and carbon (grid-intensity priced, consistent with green-MLOps); sample: 2000 reqs → $79.37 / 392g CO₂ across 4 tenants, native == reference
- [ ] PA185 Budget guardrails + spend-anomaly detection
- [ ] PA186 Rightsizing recommender (GPU utilisation → instance)
- [ ] PA187 Carbon-aware scheduler hook into admission
- [ ] PA188 Spot/preemptible fallback with checkpoint-resume
- [ ] PA189 FinOps showback/chargeback report

### DevEx, release & verification (PA190–PA198)
- [ ] PA190 Native fuzz harness for boundary parsers (libFuzzer)
- [ ] PA191 Property-based tests for native engines
- [ ] PA192 Deterministic record/replay harness for events
- [ ] PA193 Native closed-loop load generator (concurrency control)
- [ ] PA194 Golden-output contract tests across all native CLIs
- [ ] PA195 ASan/UBSan/TSan sanitizer CI lane
- [ ] PA196 Reproducible-build (bit-for-bit) verification
- [ ] PA197 Performance-regression gate wired to CI (budget diff)
- [ ] PA198 One-command production smoke (`make prod-smoke`)

### Backlog totals
Core (PA001–PA071): 71 items. Long-term (PA072–PA143): 72 items.
Wave 3 (PA144–PA198): 55 items. **198 total.**
