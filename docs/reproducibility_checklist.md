# Reproducibility Checklist

Date: 2026-06-12

Use this checklist before any final demo or report claim.

## Required Commands

- `make test`
- `make smoke`
- `make app-smoke`
- `make professor-demo-acceptance`
- `make vulnerability-scan-sample`
- `make native-ci-contract-test`
- `make native-ci-contract-sample`
- `make evaluation-index-sample`
- `make native-job-runner-test`
- `make native-job-runner-sample`
- `make vton-native-api-sample`
- `make native-slo-gate-test`
- `make native-slo-gate-sample`
- `make native-event-dispatcher-test`
- `make native-event-dispatcher-sample`
- `make native-config-contract-test`
- `make native-config-contract-sample`
- `make native-dependency-lock-contract-test`
- `make native-dependency-lock-contract-sample`
- `make native-secret-rotation-contract-test`
- `make native-secret-rotation-contract-sample`
- `make native-tls-contract-test`
- `make native-tls-contract-sample`
- `make native-tls-smoke`
- `make native-fullstack-load-test`
- `make native-fullstack-load-sample`
- `make native-quota-read-model-test`
- `make native-quota-read-model-sample`
- `make native-runtime-telemetry-test`
- `make native-runtime-telemetry-sample`
- `make native-performance-budget-test`
- `make native-performance-budget-sample`
- `make native-gguf-preflight-test`
- `make llm-gguf-preflight-sample`
- `make native-vllm-probe-test`
- `make llm-vllm-probe-sample`
- `make native-quantized-preflight-test`
- `make llm-quantized-preflight-sample`
- `make roadmap-status`
- `make native-tooling`
- `make native-rust-smoke`
- `make gateway-benchmark-native`
- `make native-policy-sample`
- `make experiment-routing-sample`
- `make experiment-analysis-sample`
- `make vton-advanced-eval-sample`
- `make llm-continuous-batching-sample`
- `make dashboard-sample`
- `docker compose config`
- `docker compose --profile tls config`

## Required Evidence

- Promotion decision: `reports/generated/<candidate_id>/promotion_decision.json`
- Dataset validation: `reports/generated/<candidate_id>/data_validation.json`
- Registry entry: `reports/generated/<candidate_id>/registry_entry.json`
- Lineage: `reports/generated/<candidate_id>/lineage.json`
- OpenLineage RunEvent: `reports/generated/<candidate_id>/openlineage_run_event.json`
- OpenLineage native validation: `reports/generated/<candidate_id>/openlineage_validation.json`
- Native policy decision: `reports/generated/<candidate_id>/native_policy_decision.json`
- Run context: `reports/generated/<candidate_id>/run_context.json`
- Model card: `reports/generated/<candidate_id>/model_card.md`
- Data card: `reports/generated/<candidate_id>/data_card.md`
- VTON comparison: `artifacts/eval/vton_comparison/comparison.json`
- VTON advanced evaluation: `artifacts/eval/vton_advanced/vton_advanced_eval_report.json`
- VTON native API execution: `artifacts/eval/vton_native_api/vton_native_api_report.json` must contain `tryops.vton_native_api.v1`, `passed=true`, available C++ person/garment preprocessing, available C++ native image metrics, a numeric `native_vton.quality_score`, `sidecar_has_native_execution=true`, and `request_detail_quality_persisted=true` so request details/dashboard rollups expose native image-quality evidence.
- VTON CLIP garment similarity: `artifacts/eval/vton_clip/garment_clip_similarity.json` must contain `tryops.garment_similarity.v1`, `clip.available=true`, `clip.backend=transformers_clip`, `clip.image_similarity`, and a `clip.best_text_prompt`.
- LLM benchmark: `artifacts/eval/llm_baseline/benchmark.json`
- LLM GPTQ/AWQ preflight: `artifacts/eval/llm_quantized/quantized_model_preflight.json` must contain `tryops.quantized_model_preflight.v1`, `summary.suitable_candidates=2`, a GPTQ candidate with `quantization.method=gptq`, an AWQ candidate with `quantization.method=awq`, 4-bit settings, reachable SafeTensors artifact checks, runtime package availability, and explicit `missing_packages` when loader runtimes are absent. Only `summary.load_ready_candidates=2` plus a separate generation benchmark can support live GPTQ/AWQ loading or speed claims.
- LLM GGUF CPU preflight: `artifacts/eval/llm_gguf/gguf_preflight.json` must contain `tryops.native_gguf_preflight.v1`, `passed=true`, `header.magic=GGUF`, `header.version=3`, non-zero `header.tensor_count`, non-zero `header.metadata_kv_count`, `selected_metadata.general.file_type_name`, and a `runtime.generation_tested` flag. If `runtime.llama_cli_available=false`, the report may prove artifact/runtime inspection but must not be used as a live generation benchmark.
- LLM vLLM serving probe: `artifacts/eval/llm_vllm/vllm_serving_probe.json` must contain `tryops.vllm_serving_probe.v1`, `environment.gpus`, `environment.vllm_binary_available`, `target.base_url`, and a status of `passed`, `failed`, or `skipped`. Only `status=passed` with successful `/v1/models`, `/v1/chat/completions`, and load results can be used as live vLLM serving evidence; `status=skipped` is readiness evidence only.
- LLM continuous batching: `artifacts/eval/llm_batching/continuous_batching_report.json`
- LLM load test: `artifacts/eval/llm_load/load_test.json`
- Deployment package: `artifacts/deployments/<package_id>/deployment_manifest.json`
- Release notes: `artifacts/deployments/<package_id>/release_notes.md`
- Rollback plan: `artifacts/deployments/<package_id>/rollback_plan.json`
- GitOps Application: `artifacts/deployments/<package_id>/gitops/application.yaml`
- GitOps Rollout: `artifacts/deployments/<package_id>/gitops/rollout.yaml`
- GitOps validation: `artifacts/deployments/<package_id>/gitops/gitops_validation.json`
- Signed promotion PR trigger: `artifacts/eval/signed_pr/signed_pr_promotion_report.json`
- Registry webhook deploy trigger: `artifacts/eval/registry_webhook/registry_webhook_report.json` must contain `native_policy.available=true`, `native_policy.wire_format=tryops.native_policy.v1`, and `native_policy.decision.approved=true` when `TRYOPS_CONTROLLER_POLICY_CLI` is configured.
- DVC/MinIO data versioning: `artifacts/eval/data_versioning/dvc_minio_report.json` must contain `tryops.dvc_minio_versioning.v1`, `passed=true`, a present `dvc.lock`, local DVC cache objects, remote MinIO cache objects, and `remote_matches_or_exceeds_local_cache=true`.
- Online experiment routing: `artifacts/eval/experiments/online_experiment_report.json`
- Online experiment analysis: `artifacts/eval/experiments/online_experiment_analysis_report.json`
- Grafana dashboard validation: `artifacts/eval/dashboards/dashboard_report.json`
- Rust gateway proxy/edge smoke: `artifacts/native/tryops-gateway.log`
- Rust gateway native metrics smoke: `make native-rust-smoke` must show `tryops_gateway_requests_total`, `tryops_gateway_request_latency_ms_bucket`, and `tryops_gateway_quota_decisions_total`
- Rust gateway semantic-cache admission and C++ edge lookup smoke: `make native-edge-cache-smoke` must show `tryops_gateway_semantic_cache_admissions_total` with both admitted and sensitive-prompt skip decisions, response headers `x-tryops-edge-cache-lookup-hit: true` and `x-tryops-edge-cache-matched-entry`, and `tryops_gateway_semantic_cache_lookups_total{source="native_cpp_cli",result="hit"}`.
- Native gateway benchmark: `artifacts/eval/gateway_benchmark/native_gateway_benchmark.json` must contain `tryops.native_gateway_benchmark.v1`, zero errors, and scenarios for `/health`, direct validated promotion POST, and full edge promotion POST.
- Native SLO regression gate: `artifacts/eval/slo/native_slo_gate_report.json` must contain `tryops.native_slo_gate.v1`, `passed=true`, and passing rules for gateway health native latency, direct promotion latency, and edge-proxy overhead using the native gateway benchmark artifact as input.
- Native event dispatcher: `artifacts/eval/events/native_event_dispatcher_report.json` must contain `tryops.native_event_dispatcher.v1`, `passed=true`, four sample event types, four audit writes, and four signed webhook deliveries; `artifacts/eval/events/native_audit_events.jsonl` must contain `tryops.native_audit_event.v1` records.
- Native config contract: `artifacts/eval/config/native_config_contract_report.json` must contain `tryops.native_config_contract.v1`, `passed=true`, all 10 enterprise services, 4 Compose secrets, required gateway/API/env contracts, Alertmanager wiring, port interpolations, healthchecks, dependency readiness conditions, named volumes, direct credential-env absence, `.env.example` coverage, and Rust gateway source references for gateway env vars.
- Native dependency lock contract: `artifacts/eval/dependencies/native_dependency_lock_contract.json` must contain `tryops.native_dependency_lock_contract.v1`, `passed=true`, `coverage_level=native_dependency_lock_contract`, `uv.lock` coverage for all `pyproject.toml` dependencies including `accelerate` and `bitsandbytes`, `web/package-lock.json` direct dependency coverage, Rust gateway `Cargo.lock` direct dependency coverage, Go checksum coverage for every native Go module with external requirements, and 0 failed checks.
- Native secret rotation contract: `artifacts/eval/secrets/native_secret_rotation_contract.json` must contain `tryops.native_secret_rotation_contract.v1`, `passed=true`, `coverage_level=native_secret_rotation_plan_contract`, 8 managed secrets, Vault KV provider details, hash-only API-key registry policy, Kubernetes workload identity with projected service-account token evidence, External Secrets coverage for every managed secret, 50/50 passing plan checks, and `production_ready=false` unless `VAULT_ADDR` plus `TRYOPS_WORKLOAD_IDENTITY_TOKEN_PATH` are configured in a live environment.
- Native Postgres migration/pool contract: `artifacts/eval/postgres/native_postgres_migration.json` must contain `tryops.native_postgres_migration.v1`, `passed=true`, `coverage_level=native_postgres_migration_pool_contract`, two idempotent migrations, required product/quota tables, 20/20 plan checks, and `pool.driver=pgxpool`; when a live Compose Postgres DSN is available, `artifacts/eval/postgres/native_postgres_migration_live.json` must contain `coverage_level=native_postgres_live_migration_pool_apply`, pooled ping/acquire success, two applied migrations, `tryops_schema_migrations`, and live table verification.
- Native backup/restore drill contract: `artifacts/eval/backup/native_backup_restore_drill.json` must contain `tryops.native_backup_restore_drill.v1`, `passed=true`, `coverage_level=native_backup_restore_plan_contract`, 20/20 plan checks, Compose `postgres-data`/`minio-data` storage validation, and `infra/backup/restore_drill.cron`; when a live Compose Postgres DSN is available, `artifacts/eval/backup/native_backup_restore_live.json` must contain `coverage_level=native_backup_restore_live_drill`, 50/50 checks, a non-empty Postgres custom-format dump, isolated `tryops_restore_drill` row-count verification for seven tables, one MinIO object restored through `mc mirror`, and cleanup of temporary restore targets.
- Native TLS termination contract: `artifacts/eval/tls/native_tls_contract.json` must contain `tryops.native_tls_contract.v1`, `passed=true`, `coverage_level=native_tls_termination_contract`, 24/24 plan checks, Compose `gateway-tls` profile validation, `TRYOPS_GATEWAY_TLS_CERT_PATH`/`TRYOPS_GATEWAY_TLS_KEY_PATH`, `tryops_tls_cert`/`tryops_tls_key` secret mounts, HTTPS healthcheck wiring, and a matching localhost/tryops.local/127.0.0.1 certificate/key pair; `artifacts/eval/tls/native_tls_contract_live.json` must contain `coverage_level=native_tls_termination_live_handshake`, 30/30 checks, `live_handshake=true`, `TLS1.3`, HTTPS `/health` status 200, and plaintext HTTP rejection on the TLS port.
- Native container image split: `artifacts/eval/containers/native_container_contract_report.json` must contain `tryops.native_container_contract.v1`, `passed=true`, seven required roles (`gateway`, `controller`, `guardrail`, `benchmark`, `cpp-tools`, `api`, `web-assets`), 89/89 passing checks, matching Compose services and Dockerfile contexts, multi-stage native build checks, non-SDK runtime checks for compiled images, Rust builder/runtime ABI-suite compatibility for Rust-containing images, source-path coverage, and Docker research/provenance links. `docker compose config` must also parse the updated Compose file.
- Native performance budget: `artifacts/eval/performance/native_performance_budget.json` must contain `tryops.native_performance_budget.v1`, `passed=true`, 11/11 passing budgets, Rust/Go/C++ language coverage, input references to gateway benchmark/SLO/config/perf artifacts, native p95/p99/RPS/throughput-ratio budgets, C++ perf SLO budgets, and executable binary checks for the Rust gateway, Go benchmark/SLO/config tools, and C++ perf stats CLI. `artifacts/eval/performance/native_performance_budget.md` must summarize the same report for CI job summaries.
- Native trace/log envelope: `artifacts/eval/trace_envelope/native_trace_envelope_report.json` must contain `tryops.native_trace_envelope.v1`, `passed=true`, `contract=tryops.native_trace_log_envelope.v1`, exactly covered languages for Rust/Go/C++/FastAPI, 4/4 passing validations, W3C Trace Context and OpenTelemetry research links, non-zero lowercase hex trace/span IDs, matching `traceparent` values, and `service.name`/`service.version` resource identity for every envelope.
- Native full-stack load SLO: `artifacts/eval/load/native_fullstack_load.json` must contain `tryops.native_fullstack_load.v1`, `passed=true`, `coverage_level=native_go_fullstack_gateway_bff_load_slo`, six product scenarios through the Rust gateway `/api/*` path, zero request errors, passing per-scenario SLOs, total request count, worst p95/p99 latency, minimum RPS, and `external_tools` records for `k6` and `locust`. If `summary.external_ready=false`, the artifact proves the native Go load gate only and must not be claimed as completed k6/locust confirmation.
- Native quota read model: `artifacts/eval/quota/native_quota_read_model.json` must contain `tryops.native_quota_read_model.v1`, `passed=true`, `coverage_level=native_quota_bff_showback_read_model`, `summary.native_source=true`, positive tenant/period/dimension counts, hashed tenant IDs only, limit/utilization/remaining fields, and tenant showback values. The BFF route `/api/quota/summary` must require admin-read auth and return the same schema.
- Native runtime telemetry: `artifacts/eval/runtime/native_runtime_telemetry.json` must contain `tryops.native_runtime_telemetry.v1`, `passed=true`, `coverage_level=native_go_llm_gpu_runtime_exporter`, benchmark tokens/sec, Pareto variant tokens/sec, peak VRAM values, native SLO stats present, and at least one `nvidia-smi` GPU snapshot when NVIDIA hardware is available. `artifacts/eval/runtime/native_runtime_telemetry.prom` must expose `tryops_llm_tokens_per_second`, `tryops_llm_peak_vram_gb`, `tryops_gpu_memory_used_bytes`, `tryops_gpu_memory_total_bytes`, `tryops_gpu_utilization_ratio`, and `tryops_gpu_power_watts`.
- Native observability contract: `artifacts/eval/observability/native_observability_contract.json` must contain `tryops.native_observability_contract.v1`, `passed=true`, 3 Collector pipelines, OTLP gRPC/HTTP receivers, JSONL filelog ingestion, file exporters, Compose `otel-collector` service, Prometheus `tryops-otel-collector` scrape target, gateway/API service names, a shared trace ID, model-call metadata, and redaction checks. `make native-observability-contract-sample` must generate the report from `infra/otel/collector.yml`, `docker-compose.yml`, `infra/prometheus/prometheus.yml`, `artifacts/logs/gateway_events.jsonl`, and `artifacts/eval/traces/*.jsonl`.
- Native Alertmanager contract: `artifacts/eval/alerts/native_alertmanager_contract.json` must contain `tryops.native_alertmanager_contract.v1`, `passed=true`, `coverage_level=native_alertmanager_routing_contract`, 16 alert rules, Alertmanager page/ticket receivers, severity/workload/alertname grouping, page/ticket matchers, inhibition, Prometheus `alertmanager:9093` forwarding, Compose `alertmanager` service, and controller webhook target `http://controller:18082/alerts/webhook`.
- Full stack startup smoke: `make app-smoke` must run under the disposable Compose project `tryops_app_smoke`, recreate the smoke volumes before startup, and remove them on exit so stale local default volumes cannot taint the result. `artifacts/eval/full_stack/full_stack_smoke.json` must contain `tryops.full_stack_smoke.v1`, `passed=true`, and checks for Console, SPA fallback, gateway/API health/readiness, LLM generation, VTON comparison JSON, VTON artifact PNG serving, optimization-panel serving, native edge-auth missing-key and missing-scope rejection, pipeline-run ledger serving, bad-candidate promotion rejection, rollback-state artifact serving through the Rust gateway, gateway metrics, guardrail, Prometheus, Grafana, MinIO, and MLflow.
- Professor demo acceptance: `artifacts/eval/demo_acceptance/professor_demo_acceptance.json` must contain `tryops.professor_demo_acceptance.v1`, `passed=true`, a live blocked bad-candidate gate, and evidence checks for LLM Pareto, energy, full-stack smoke, native quota ledger, VTON comparison, lineage, promotion, rollback, governance, the Console Professor Demo view, and the seeded demo data contract.
- Professor demo backup video: `artifacts/eval/demo_video/professor_demo_video.json` must contain `tryops.professor_demo_video.v1`, `passed=true`, `frame_count >= 9`, `step_count >= 7`, `duration_seconds > 0`, and `video_path=artifacts/demo/professor_demo_video/professor_demo_backup.mp4`; FFprobe must report H.264 video at 1280x720 and 30 FPS.
- Vulnerability scan: `artifacts/eval/security/vulnerability_scan_report.json` must contain `tryops.vulnerability_scan.v1`, `passed=true`, the installed-tool scan results, and explicit `missing_required_tools` when enterprise scanners are absent.
- Native CI supply-chain contract: `artifacts/eval/ci/native_ci_contract.json` must contain `tryops.native_ci_contract.v1`, `passed=true`, workflow path `.github/workflows/ci.yml`, `make ci` coverage, GitHub Actions OIDC permissions, upload-artifact evidence, seven-image Docker Buildx matrix, Syft SPDX SBOM generation, Trivy HIGH/CRITICAL scan gate, Cosign keyless signing on non-PR pushes, and schema references to vulnerability, supply-chain, and container-contract reports. If `production_ready=false`, the report must list missing required local tools and cannot be used as live Syft/Trivy/Cosign execution evidence.
- Evaluation index: `artifacts/eval/evaluation_index/evaluation_index.json` must contain `tryops.evaluation_index.v1`, report counts, highlighted Pareto/energy/VTON/native-VTON-API/drift/full-stack/demo/security/CI/dependency-lock/config/secrets/postgres/backup/tls/container/performance/fullstack-load/trace-envelope/observability/alertmanager/quota-read-model/runtime-telemetry evidence, `pipeline_runs` from run-context/OpenLineage/lineage artifacts, `optimization_panel` with `recommended_variant="4bit"`, `carbon_gate_verdict="pass"`, per-variant energy and SCI metrics, native SLO gate evidence, native event-dispatcher evidence, native CI contract evidence, native dependency-lock evidence, native config-contract evidence, native secret-rotation evidence, native Postgres migration evidence, native backup/restore drill evidence, native TLS termination evidence, native container-contract evidence, native trace-envelope evidence, native full-stack load SLO evidence, native observability evidence, native Alertmanager evidence, native quota-read-model evidence, native runtime-telemetry evidence, native performance-budget evidence, and the Console endpoint `/api/evaluations/summary` must pass through `make app-smoke`.
- Native Go job runner: `artifacts/eval/jobs/native_job_runner_report.json` must contain `tryops.native_job_runner.v1`, `passed=true`, one passed LLM direct-generation job, one passed async VTON job with a non-empty `job_id`, context-bound HTTP attempts, retry attempt counts, and at least one VTON poll.
- Console pipeline run history: the Runs view must render the `pipeline_runs` ledger from `/api/evaluations/summary`; `make app-smoke` must require `pipeline_runs`, `run-vton-001`, and `COMPLETE` in the gateway response.
- Console optimization panel: the Evaluation view must render the `optimization_panel` from `/api/evaluations/summary`; `make app-smoke` must require `optimization_panel`, `recommended_variant":"4bit"`, and `carbon_gate_verdict":"pass"` in the gateway response.
- Rust gateway auth preflight: protected `/api/*` routes must be denied by the gateway before FastAPI when credentials are missing or under-scoped; `make app-smoke` must include `gateway_auth_preflight_rejects_missing_key` with HTTP 401, `gateway_auth_preflight_rejects_missing_scope` with HTTP 403, and `gateway_metrics` must expose `tryops_gateway_auth_decisions_total`.
- RBAC session and role-aware nav: `configs/api_keys.json` must include active viewer/operator/admin principals with `session:read`; `/api/auth/session` and `/v1/auth/session` must return `tryops.rbac_session.v1` with allowed nav items; the Rust gateway must require `session:read` for `/v1/auth/session`; the Console must filter navigation from `session.permissions.nav`; `tests.test_auth`, `tests.test_api_surface`, `cargo test --manifest-path native/rust/tryops-gateway/Cargo.toml auth`, and `npm run typecheck` must pass.
- VTON comparison artifact serving: `/api/vton/comparison?api_key=tryops-viewer-demo-key` must return `tryops.vton_comparison.v1` with `output_url`, and `/api/artifacts/file?path=artifacts/eval/vton_comparison/naive_standard.png&api_key=tryops-viewer-demo-key` must return a PNG signature of `89504e470d0a1a0a` through the Rust gateway.
- Console bad-model gate: the Incident view must run the seeded candidate from `web/src/data.ts` through `/api/promotion/evaluate` with `x-tryops-artifact-signed: true`; `make app-smoke` must include `bad_candidate_gate_through_gateway` with `approved=false`, role `risk_reviewer`, and rejection reasons for unsigned artifact/provenance/vulnerability failures.
- Console rollback drill: the Incident view must load `artifacts/deployments/rollback_state.json` through `/api/artifacts/file`; `make app-smoke` must include `rollback_state_artifact_through_gateway` with `tryops.rollback_state.v1`, `tryops.rollback_record.v1`, and the restored candidate ID.

## Run Context Requirements

Every generated run should include:

- run ID
- trace ID
- code version or explicit local-unversioned status
- Python/runtime environment
- hardware summary

Because this workspace is not currently a real Git repository, the code version may be
`local-dev-unversioned`. A final submission should set `TRYOPS_CODE_VERSION` or run inside a real
Git checkout.

## Report Claims

Do not claim:

- real VTON model quality until CatVTON/IDM-VTON or another neural adapter is executed
- real LLM quality until SmolLM2 or another neural model is executed
- live GPTQ/AWQ loading, live GGUF generation, or live vLLM serving speedups until those variants are benchmarked
- production continuous-batching gains beyond the native scheduler model until a live vLLM server benchmark is run
- production Rust hardening claims beyond the local `cargo test`, release build, and gateway smoke evidence
