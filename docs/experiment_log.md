# Experiment Log

Date: 2026-06-11

## EXP-001: Local Promotion Pipeline

- Command: `make pipeline-sample`
- Workload: VTON
- Candidate: `vton-catvton-2026-06-11-001`
- Evidence directory: `reports/generated/vton-catvton-2026-06-11-001`
- Outcome: promotion approved by local policy gates
- Notes: validates registry entry, lineage, model card, data card, data validation, and run context

## EXP-002: Synthetic VTON Baseline Comparison

- Command: `make vton-compare-sample`
- Workload: VTON
- Evidence directory: `artifacts/eval/vton_comparison`
- Outcome: compares two deterministic overlay configurations and writes an error-gallery artifact
- Notes: smoke proxy only; does not claim CatVTON or IDM-VTON neural quality

## EXP-003: Local LLM Golden-Prompt Benchmark

- Command: `make llm-benchmark-sample`
- Workload: LLM
- Evidence file: `artifacts/eval/llm_baseline/benchmark.json`
- Outcome: validates structured output, safety refusal behavior, latency, tokens/sec, memory, quality checks, and cost fields
- Notes: deterministic contract baseline only; SmolLM2/vLLM execution remains future work

## EXP-004: Deployment Package and Release Notes

- Command: `make deploy-package-sample`
- Workload: release engineering
- Evidence directory: `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo`
- Outcome: writes deployment manifest, release notes, and rollback plan from promotion evidence
- Notes: package includes native C++ policy evidence when `artifacts/native/tryops_policy_cli` is built

## EXP-005: Local LLM Concurrency Load Test

- Command: `make llm-load-sample`
- Workload: LLM
- Evidence file: `artifacts/eval/llm_load/load_test.json`
- Outcome: measures local concurrent request throughput and output-token throughput
- Notes: not a vLLM batching benchmark; useful for release smoke and API contract load shape

## EXP-006: Native C++ Policy Bridge

- Command: `make native-policy-sample`
- Workload: model governance
- Evidence files:
  - `artifacts/native/tryops_policy_cli`
  - `reports/generated/vton-catvton-2026-06-11-001/native_policy_decision.json`
- Outcome: native C++ policy decision matches the Python promotion gate for the sample champion candidate
- Notes: Go controller and guardrail sidecar build/smoke locally; the Rust gateway now also
  rebuilds, tests, and smokes locally as a modular Axum edge crate.

## EXP-007: Rollback Drill

- Command: `make rollback-sample`
- Workload: release engineering
- Evidence files:
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/rollback_record.json`
  - `artifacts/deployments/rollback_state.json`
- Outcome: records restoration target and rollback reason for the production-demo package
- Notes: local rollback is a state record; the future Go controller should reconcile this into runtime routing

## EXP-008: Native C++ Image Metrics

- Command: `make native-image-metrics-sample`
- Workload: VTON evaluation
- Evidence files:
  - `artifacts/native/tryops_image_metrics_cli`
  - `artifacts/eval/vton_comparison/comparison.json`
- Outcome: computes native MSE, PSNR, dHash similarity, and edge-delta proxy for synthetic VTON output
- Notes: dHash is a dependency-free perceptual proxy; LPIPS and CLIP remain future neural metrics

## EXP-009: Native C++ VTON Preprocessing

- Command: `make vton-preprocess-sample`
- Workload: VTON preprocessing
- Evidence files:
  - `artifacts/native/tryops_vton_preprocess_cli`
  - `artifacts/cache/vton_preflight/optional_preprocessing/*/preprocessing.json`
  - `artifacts/cache/vton_preflight/optional_preprocessing/*/person_mask.png`
  - `artifacts/cache/vton_preflight/optional_preprocessing/*/garment_mask.png`
- Outcome: emits optional person/garment masks, heuristic pose hints, checksums, latency, and native C++ preprocessing evidence
- Notes: this is a dependency-free compatibility bridge for model adapters that need masks or pose; production quality should come from SAM/SCHP/DensePose/OpenPose adapters

## EXP-010: Garment Similarity Proxy

- Command: `make vton-garment-similarity-sample`
- Workload: VTON evaluation
- Evidence files:
  - `artifacts/demo/vton/output.png.json`
  - `artifacts/eval/vton_comparison/comparison.json`
- Outcome: records garment-patch similarity and OpenCLIP dependency readiness in VTON comparison artifacts
- Notes: This early proxy-only experiment has since been superseded by EXP-068, which verifies neural CLIP scoring through the Transformers CLIP backend; OpenCLIP itself remains optional until local OpenCLIP weights are pinned.

## EXP-011: LLM Length Sensitivity

- Command: `make llm-sensitivity-sample`
- Workload: LLM optimization
- Evidence file: `artifacts/eval/llm_sensitivity/sensitivity.json`
- Outcome: records prompt-length and output-length sensitivity for the local deterministic baseline
- Notes: this validates the benchmark harness and report contract; neural vLLM, Transformers, GPTQ, AWQ, and GGUF variants still need separate runs

## EXP-012: Usage-Based Quota Accounting

- Command: `make quota-sample`
- Workload: enterprise serving controls
- Evidence file: `artifacts/eval/quota/quota_usage.json`
- Outcome: records Rust gateway quota decisions for per-user hashed LLM request/token usage and VTON request usage
- Notes: `tryops-gateway quota-check` now owns the quota arithmetic for local evidence; the gateway also has optional Postgres/Valkey-compatible mirrors, while distributed multi-gateway admission remains production validation

## EXP-013: Optimized LLM Fallback Routing

- Command: `make llm-fallback-sample`
- Workload: LLM optimization
- Evidence file: `artifacts/eval/llm_fallback/fallback.json`
- Outcome: switches an unavailable optimized alias back to the baseline route and records the pre-fallback alias, health status, and reason
- Notes: local routing simulates optimized model readiness; live vLLM or quantized model health checks remain future work

## EXP-014: Async VTON Job Mode

- Command: `make vton-job-sample`
- Workload: VTON serving
- Evidence file: `artifacts/eval/vton_jobs/job.json`
- Outcome: submits a VTON job, polls status to completion, returns the synchronous VTON result shape, and verifies queue-depth metrics are exposed
- Notes: local evidence uses an in-memory queue; production should use a durable queue and Go/Rust control-plane reconciliation

## EXP-015: Alert Threshold Evaluation

- Command: `make alert-sample`
- Workload: observability
- Evidence files:
  - `configs/alert_thresholds.json`
  - `artifacts/eval/alerts/alert_report.json`
  - `infra/prometheus/tryops_alerts.yml`
- Outcome: evaluates local LLM/VTON latency and quality thresholds and writes Prometheus-style alert rules
- Notes: local threshold evaluation reads release artifacts; Alertmanager routing is now wired in
  EXP-081, while production still needs live Prometheus series and external notification
  credentials.

## EXP-016: Grafana Dashboard Provisioning

- Command: `make dashboard-sample`
- Workload: observability
- Evidence files:
  - `infra/grafana/provisioning/datasources/prometheus.yml`
  - `infra/grafana/provisioning/dashboards/tryops.yml`
  - `infra/grafana/dashboards/tryops-service-overview.json`
  - `infra/grafana/dashboards/tryops-model-quality.json`
  - `infra/grafana/dashboards/tryops-cost-capacity.json`
  - `artifacts/eval/dashboards/dashboard_report.json`
- Outcome: validates that service, model-quality, and cost/capacity dashboards are provisioned with the stable Prometheus datasource UID
- Notes: service panels use live local API metrics; quality and cost panels reserve production metric names for later exporters

## EXP-017: Input Drift Reports

- Command: `make drift-sample`
- Workload: observability
- Evidence files:
  - `artifacts/eval/drift/image_metadata_drift.json`
  - `artifacts/eval/drift/prompt_topic_drift.json`
  - `artifacts/eval/drift/drift_summary.json`
- Outcome: compares VTON image metadata and LLM prompt descriptors between reference and deterministic current windows
- Notes: current windows are simulated for local reproducibility; production should feed sanitized request metadata into the same report contract

## EXP-018: Endpoint Smoke Test

- Command: `make endpoint-smoke-sample`
- Workload: serving
- Evidence files:
  - `artifacts/eval/endpoint_smoke/deployed_endpoint_smoke.json`
  - `artifacts/eval/endpoint_smoke/vton_output.png`
- Outcome: verifies readiness, LLM generation, VTON inference, and metrics endpoints through the `/v1` contract
- Notes: local mode calls FastAPI route handlers in process; pass `--base-url` to smoke test a running deployed API

## EXP-019: Governance Risk Mapping

- Command: `make governance-sample`
- Workload: governance
- Evidence files:
  - `configs/governance_risk_controls.json`
  - `artifacts/eval/governance/governance_report.json`
  - `docs/responsible_ai_risk_mapping.md`
- Outcome: maps the local risk register to NIST AI RMF functions, maps LLM controls to OWASP Top 10 for LLM Applications 2025, and records responsible-AI residual risks
- Notes: generated evidence is a governance map; it does not replace live SBOM/scanning/signing or human approval workflows

## EXP-020: Least-Privilege Admin API Keys

- Command: `make auth-sample`
- Workload: security and governance
- Evidence files:
  - `configs/api_keys.json`
  - `artifacts/eval/auth/api_key_auth_report.json`
- Outcome: verifies scoped admin authorization for promotion and lineage actions with redacted authorization decisions
- Notes: local registry stores SHA-256 hashes only; production should replace static demo keys with OIDC, workload identity, or gateway-level secret validation

## EXP-021: Supply-Chain Lock And SBOM Evidence

- Command: `make supply-chain-sample`
- Workload: security and governance
- Evidence files:
  - `uv.lock`
  - `requirements.lock`
  - `artifacts/eval/dependencies/native_dependency_lock_contract.json`
  - `configs/model_sources.json`
  - `configs/dataset_licenses.json`
  - `artifacts/eval/supply_chain/dependency_lock.json`
  - `artifacts/eval/supply_chain/sbom.spdx.json`
  - `artifacts/eval/supply_chain/supply_chain_report.json`
- Outcome: pins the full Python project resolution in `uv.lock`, preserves the legacy
  `requirements.lock` fallback for the local SPDX generator, writes a local SPDX 2.3 SBOM fallback,
  audits model-source licenses, and records dataset usage restrictions.
- Notes: Syft, Trivy, Grype, and pip-audit are not installed locally, so CVE-backed vulnerability scanning remains open

## EXP-022: Kubeflow-Target Orchestration Skeleton

- Command: `make orchestration-sample`
- Workload: pipelines and release automation
- Evidence files:
  - `artifacts/eval/orchestration/tryops_pipeline_dag.json`
  - `artifacts/eval/orchestration/tryops_pipeline.kfp.yaml`
  - `artifacts/eval/orchestration/orchestration_report.json`
- Outcome: emits a validated seven-step DAG covering data validation, VTON evaluation, LLM benchmarking, supply-chain evidence, governance mapping, promotion, and deployment packaging
- Notes: local evidence is a Kubeflow-target skeleton; live KFP compile/upload and Kubernetes execution remain future work

## EXP-023: LLM Optimization Pareto Report

- Command: `make llm-optimization-report-sample`
- Workload: LLM optimization
- Evidence files:
  - `artifacts/eval/llm_optimization_report/llm_optimization_report.md`
  - `artifacts/eval/llm_optimization_report/llm_pareto_chart.svg`
  - `artifacts/eval/llm_optimization_report/llm_pareto_metrics.csv`
  - `artifacts/eval/llm_optimization_report/llm_optimization_report.json`
- Outcome: turns the measured `tryops.llm_pareto.v1` artifact into a quality-latency-memory report and Pareto chart
- Notes: current report covers fp16-style, bitsandbytes 8-bit, and bitsandbytes 4-bit only; GPTQ, AWQ, live GGUF generation, and live vLLM remain open. Native continuous-batching scheduler evidence is tracked separately in EXP-040, and native GGUF artifact preflight is tracked separately in EXP-070.

## EXP-024: LLM Prefill And Decode Timing

- Command: `make llm-benchmark-sample`
- Workload: LLM observability
- Evidence files:
  - `artifacts/eval/llm_baseline/benchmark.json`
  - `docs/llm_phase_timing.md`
- Outcome: records `tryops.llm_phase_timing.v1` prefill/decode fields per LLM benchmark record and summary phase p95/average values
- Notes: deterministic baseline phase timing is a local contract split; low-level neural prefill/decode tracing should move to vLLM or backend-specific instrumentation

## EXP-025: OpenTelemetry-Compatible Trace Spans

- Command: `make trace-sample`
- Workload: observability
- Evidence files:
  - `artifacts/eval/traces/trace_sample.json`
  - `artifacts/eval/traces/api_spans.jsonl`
  - `artifacts/eval/traces/api_events.jsonl`
  - `docs/opentelemetry_tracing.md`
- Outcome: verifies W3C-compatible `traceparent` propagation, local `tryops.trace_span.v1` server spans, structured-log trace correlation, Prometheus trace metrics, and privacy checks that keep raw prompts and image paths out of trace records
- Notes: local spans are Collector-ready evidence; production still needs OTLP exporter/Collector wiring, preferably at the Rust gateway boundary

## EXP-026: Native SLO Burn-Rate Evaluation

- Command: `make slo-burn-rate-sample`
- Workload: reliability
- Evidence files:
  - `configs/service_level_objectives.json`
  - `artifacts/eval/slo/slo_burn_rate_report.json`
  - `infra/prometheus/tryops_burn_rate_alerts.yml`
  - `artifacts/native/tryops_burn_rate_cli`
- Outcome: evaluates LLM, VTON, and control-plane error-budget burn rates with the native C++ engine and verifies that the current local evidence is not firing while a deterministic regression drill produces a page verdict
- Notes: current windows are computed from local artifacts; production should replace them with live Prometheus SLI windows and route page/ticket alerts through Alertmanager

## EXP-027: Native LLM Guardrail Runtime

- Command: `make guardrail-sample`; `make native-guardrail-smoke`
- Workload: LLM security runtime
- Evidence files:
  - `native/go/tryops-guardrail/*.go`
  - `artifacts/native/tryops_guardrail_cli`
  - `artifacts/eval/guardrails/guardrail_report.json`
  - `infra/grafana/dashboards/tryops-guardrails.json`
  - `docs/llm_guardrails.md`
- Outcome: enforces runtime PII redaction, prompt-injection blocking, system-prompt leakage blocking, unbounded-consumption blocking, output-safety checks, and structured-output validation through a native Go sidecar/CLI with Python fallback only for offline determinism
- Notes: Compose now runs the guardrail as an independent Go sidecar and Prometheus scrape target; production should replace deterministic patterns with a model-backed Prompt Guard/Llama Guard service when weights and latency budgets are approved

## EXP-028: Native Model Artifact Supply-Chain Gate

- Command: `make model-supply-chain-sample`
- Workload: model supply chain
- Evidence files:
  - `native/cpp/tryops_model_scan/src/tryops_model_scan_cli.cpp`
  - `artifacts/native/tryops_model_scan_cli`
  - `artifacts/eval/model_supply_chain/model_supply_chain_report.json`
  - `artifacts/eval/model_supply_chain/safe_model_artifact_scan.json`
  - `artifacts/eval/model_supply_chain/unsafe_model_artifact_scan.json`
  - `docs/model_supply_chain.md`
- Outcome: a valid `.safetensors` sample passes the native scanner and both promotion gates; an unsafe `pytorch_model.bin` sample fails the native scanner and is rejected by both Python and native C++ promotion gates with matching reasons
- Notes: local deterministic scanning rejects pickle-family and unallowlisted formats without
  deserializing them; local DSSE-shaped provenance and native verification are now implemented,
  while production should add ModelScan/Fickling execution plus real Sigstore keyless OIDC/Rekor
  verification

## EXP-029: FinOps Budget Gates And Native Semantic Cache

- Command: `make finops-sample`
- Workload: LLM and VTON FinOps
- Evidence files:
  - `native/cpp/tryops_semantic_cache/include/tryops_semantic_cache.hpp`
  - `native/cpp/tryops_semantic_cache/src/tryops_semantic_cache.cpp`
  - `native/cpp/tryops_semantic_cache/src/tryops_semantic_cache_cli.cpp`
  - `native/cpp/tryops_semantic_cache/tests/test_semantic_cache.cpp`
  - `artifacts/native/tryops_semantic_cache_cli`
  - `artifacts/eval/finops/finops_report.json`
  - `artifacts/eval/finops/unit_economics.json`
  - `artifacts/eval/finops/budget_showback.json`
  - `artifacts/eval/finops/semantic_cache_report.json`
  - `infra/prometheus/tryops_finops_alerts.yml`
  - `infra/grafana/dashboards/tryops-cost-capacity.json`
- Outcome: produces unit economics, hashed-tenant showback, budget allow/warn/block decisions, native semantic-cache lookup evidence, and cache hit/token/cost/energy savings; the current sample reports 2 hits, 1 miss, 132 tokens saved, and no default-budget violations
- Notes: local embeddings are deterministic lexical vectors for offline repeatability; quota and cache admission now sit in the Rust gateway with Postgres/Valkey-compatible quota mirrors, while production cache lookup still needs a neural vector index such as FAISS or Qdrant

## EXP-030: Native Chaos Drill And Auto Rollback

- Command: `make chaos-sample`
- Workload: ML service reliability
- Evidence files:
  - `native/cpp/tryops_chaos/src/tryops_chaos_cli.cpp`
  - `artifacts/native/tryops_chaos_cli`
  - `artifacts/native/tryops_burn_rate_cli`
  - `artifacts/eval/chaos/chaos_drill_report.json`
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/auto_rollback_record.json`
  - `artifacts/deployments/rollback_state.json`
  - `docs/chaos_reliability.md`
- Outcome: classifies GPU OOM, slow decode, corrupted weights, and poisoned-candidate faults in native C++; each scenario crosses the native burn-rate page threshold and triggers the existing rollback record path
- Notes: local faults are deterministic SLI-window injections; production should map the same scenarios to Chaos Mesh or LitmusChaos experiments and reconcile rollback through the Go controller or rollout controller

## EXP-031: Native Gateway And Controller Verification

- Command: `make gateway-benchmark`; `make native-go-test`; `make native-go-smoke`
- Workload: production boundary
- Evidence files:
  - `artifacts/native/tryops-gateway`
  - `artifacts/eval/gateway_benchmark/gateway_benchmark.json`
  - `native/go/tryops-controller/*.go`
  - `artifacts/native/tryops-controller`
- Outcome: benchmarks the Rust Axum gateway artifact against Python FastAPI on the same `/health`
  handler (4,526 vs 2,098 req/s, 2.16x throughput) and verifies the Go controller with unit tests
  plus HTTP 202 for accepted reconcile requests and HTTP 422 for invalid requests
- Notes: the benchmark uses the compiled Rust gateway artifact, and the modular Rust gateway now
  rebuilds, tests, and smokes locally alongside the Go controller and guardrail sidecar.

## EXP-032: Model Provenance And Native Signature Verification

- Command: `make model-supply-chain-sample`
- Workload: model supply chain
- Evidence files:
  - `native/cpp/tryops_model_provenance/src/tryops_model_provenance_cli.cpp`
  - `artifacts/native/tryops_model_provenance_cli`
  - `artifacts/eval/model_supply_chain/model_provenance.json`
  - `artifacts/eval/model_supply_chain/model_provenance.intoto.json`
  - `artifacts/eval/model_supply_chain/model_signature_bundle.json`
  - `policies/model_promotion.rego`
- Outcome: binds the safe SafeTensors weight to a local DSSE-shaped signature bundle and
  in-toto/SLSA provenance statement; native C++ verifies artifact digest, payload digest, signer
  identity, and SLSA predicate before Python/C++ promotion gates accept the candidate
- Notes: this is offline evidence shaped for OpenSSF Model Signing / Sigstore model-transparency;
  production still needs real keyless OIDC identity and Rekor transparency-log verification

## EXP-033: OpenLineage RunEvent Emission And Native Validation

- Command: `make pipeline-sample`
- Workload: promotion lineage
- Evidence files:
  - `src/tryops/lineage.py`
  - `src/tryops/native_openlineage.py`
  - `native/cpp/tryops_openlineage/src/tryops_openlineage_cli.cpp`
  - `reports/generated/vton-catvton-2026-06-11-001/openlineage_run_event.json`
  - `reports/generated/vton-catvton-2026-06-11-001/openlineage_validation.json`
- Outcome: writes an OpenLineage RunEvent beside the internal TryOps `lineage.json`, mapping the
  promotion job, deterministic run UUID, dataset input, model input, and promotion-decision output.
  The native C++ validator emits `tryops.native_openlineage.v1` and passes before deployment
  packaging carries the evidence forward.
- Notes: this is local file emission and native envelope validation; a production deployment would
  POST the same event to Marquez or another OpenLineage-compatible backend.

## EXP-034: GitOps Manifests And Native Canary Validation

- Command: `make deploy-package-sample`
- Workload: deployment packaging
- Evidence files:
  - `src/tryops/gitops.py`
  - `src/tryops/native_gitops.py`
  - `native/cpp/tryops_gitops/src/tryops_gitops_cli.cpp`
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/application.yaml`
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/rollout.yaml`
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/services.yaml`
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/gitops_validation.json`
- Outcome: deployment packaging now emits an Argo CD Application, Argo Rollouts canary Rollout,
  stable/canary Services, and Kustomization file. The native C++ validator checks the Application
  source/destination/sync policy, Rollout canary services and `setWeight`/`pause` steps, candidate
  labels, and service count before the deployment manifest marks GitOps validation passed.
- Notes: this is declarative local GitOps evidence; a production cluster would let Argo CD reconcile
  the same manifests from a signed Git branch.

## EXP-035: Registry Webhook Deploy Trigger

- Command: `make registry-webhook-sample`
- Workload: deployment automation
- Evidence files:
  - `native/go/tryops-controller/*.go`
  - `scripts/simulate_registry_webhook.py`
  - `artifacts/eval/registry_webhook/registry_webhook_report.json`
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/deployment_manifest.json`
- Outcome: starts the Go controller, posts a signed MLflow-style `model_version_alias.created`
  event, verifies the HMAC signature and timestamp freshness, and returns HTTP 202 with actions to
  load the deployment package, trigger GitOps sync, and start an Argo Rollouts canary.
- Notes: the sample proves the controller contract locally; production should store webhook secrets
  in Kubernetes secrets, deduplicate delivery IDs, and reconcile the returned actions through Argo CD
  or a controller-runtime reconciler.

## EXP-036: Signed Promotion PR Trigger

- Command: `make signed-pr-promotion-sample`
- Workload: promotion automation
- Evidence files:
  - `native/go/tryops-controller/*.go`
  - `scripts/simulate_signed_pr_promotion.py`
  - `artifacts/eval/signed_pr/signed_pr_promotion_report.json`
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/deployment_manifest.json`
- Outcome: starts the Go controller, posts a GitHub-style signed `pull_request.closed` event, verifies
  the `X-Hub-Signature-256` HMAC over the raw payload, checks that the PR is merged to `main`, and
  requires approval, verified commit, status checks, native policy, OpenLineage, GitOps, and model
  provenance evidence before returning HTTP 202 promotion and registry-alias actions.
- Notes: the local event embeds approval/check evidence so smoke stays offline; a production GitHub
  App should fetch reviews, branch protection, commit verification, and check-suite conclusions
  directly from GitHub before reconciling the promotion.

## EXP-037: Native Online Experiment Router

- Command: `make experiment-routing-sample`
- Workload: LLM route selection
- Evidence files:
  - `native/cpp/tryops_experiment_router/src/tryops_experiment_router_cli.cpp`
  - `src/tryops/native_experiment_router.py`
  - `src/tryops/routing.py`
  - `scripts/evaluate_online_experimentation.py`
  - `artifacts/eval/experiments/online_experiment_report.json`
- Outcome: compiles `tryops_experiment_router_cli`, routes A/B and bandit decisions through the
  native engine, blocks the guardrail-violating `candidate` variant, and shifts/serves bandit
  traffic to `challenger` based on UCB-style reward and exploration scores.
- Notes: this keeps the hot online-routing decision path off Python while preserving the existing
  routing-layer alias contract and an offline deterministic fallback for tests.

## EXP-038: Native Online Experiment Analysis

- Command: `make experiment-analysis-sample`
- Workload: LLM experiment statistics
- Evidence files:
  - `native/cpp/tryops_experiment_stats/src/tryops_experiment_stats_cli.cpp`
  - `src/tryops/native_experiment_stats.py`
  - `scripts/evaluate_online_experiment_analysis.py`
  - `artifacts/eval/experiments/online_experiment_analysis_report.json`
- Outcome: compiles `tryops_experiment_stats_cli`, compares `champion` and `challenger` against a
  `champion_holdback` group, computes Agresti-Caffo uplift confidence intervals, and emits
  Wald-style SPRT early-stop decisions. The challenger CI excludes zero and crosses the SPRT upper
  boundary; the champion comparison does not beat the challenger.
- Notes: the report also calls native `tryops_eval_stats` for a Theme-N bootstrap CI over block-level
  uplift deltas, keeping both online experimentation statistics and evaluation statistics on the
  compiled boundary.

## EXP-039: Native VTON Advanced Evaluation And Fairness

- Command: `make vton-advanced-eval-sample`
- Workload: VTON evaluation and responsible AI
- Evidence files:
  - `native/cpp/tryops_vton_eval/src/tryops_vton_eval_cli.cpp`
  - `src/tryops/native_vton_eval.py`
  - `samples/eval/vton_preference_study.json`
  - `scripts/evaluate_vton_advanced.py`
  - `artifacts/eval/vton_advanced/vton_advanced_eval_report.json`
  - `reports/generated/vton-catvton-2026-06-11-001/model_card.md`
- Outcome: compiles `tryops_vton_eval_cli`, computes native identity embedding-proxy distance,
  masked garment-region fidelity, pose consistency, skin-tone/body-type fairness gaps, and a
  Bradley-Terry preference ranking. The generated model card is updated with advanced-evaluation,
  fairness, bias, and limitation notes.
- Notes: the current study fixture is seeded local smoke evidence; production should replace the
  identity proxy with a pinned neural face-embedding model, replace perceptual proxies with LPIPS or
  comparable learned metrics, and replace seeded slices with a representative human evaluation panel.

## EXP-040: Native LLM Continuous Batching Scheduler

- Command: `make llm-continuous-batching-sample`
- Workload: LLM serving optimization
- Evidence files:
  - `native/cpp/tryops_batch_scheduler/src/tryops_batch_scheduler_cli.cpp`
  - `src/tryops/native_batch_scheduler.py`
  - `scripts/evaluate_continuous_batching.py`
  - `artifacts/eval/llm_batching/continuous_batching_report.json`
  - `docs/llm_continuous_batching.md`
- Outcome: compiles `tryops_batch_scheduler_cli`, builds a 20-request mixed prompt/decode workload
  from the local sensitivity artifact, and compares static request-level batching with
  iteration-level continuous batching in native C++. Current local evidence records 1.218x modeled
  throughput, 19.1% lower p95 latency, and decode-slot utilization 0.623 -> 1.0.
- Notes: this proves local scheduler behavior and keeps the batch-admission comparison off Python.
  It does not replace the separate live vLLM serving benchmark tracked by E011.

## EXP-041: Energy And Cost Correlation Dashboard

- Command: `make dashboard-sample`
- Workload: Green MLOps observability
- Evidence files:
  - `infra/grafana/dashboards/tryops-cost-capacity.json`
  - `src/tryops/dashboards.py`
  - `tests/test_dashboards.py`
  - `artifacts/eval/dashboards/dashboard_report.json`
  - `docs/green_mlops.md`
- Outcome: adds Energy per 1k Tokens, CO2e per 1k Tokens, and Cost vs Energy Correlation panels to
  the cost/capacity dashboard, with validator requirements and a focused test for the Prometheus
  metric names.
- Notes: local evidence is generated from energy artifacts; production should export
  `tryops_energy_wh_per_1k_tokens`, `tryops_co2e_g_per_1k_tokens`, and
  `tryops_request_cost_usd_per_1k_tokens`.

## EXP-042: Native Rust Gateway Product Edge

- Command: `make native-rust-smoke`
- Workload: Production edge and service wiring
- Evidence files:
  - `native/rust/tryops-gateway/src/*.rs`
  - `Dockerfile.gateway`
  - `docker-compose.yml`
  - `Makefile`
  - `artifacts/native/tryops-gateway`
- Outcome: the Axum gateway now proxies public `/api/*` requests to backend `/v1/*` routes,
  injects or forwards `x-request-id`, enforces native per-key minute rate limits, applies request
  body limits, blocks admin promotion/model routes unless `x-tryops-artifact-signed: true` is
  present, and keeps quota admission native through `/v1/quota/check`.
- Notes: `docker compose config` validates the product stack wiring, and the gateway binary exposes a
  `health-check` mode for container healthchecks. The end-user React console and persisted product
  BFF routes are still tracked separately under P2/P3.

## EXP-043: Native Rust Gateway Prometheus Exporter

- Command: `make native-rust-smoke`
- Workload: Production edge observability
- Evidence files:
  - `native/rust/tryops-gateway/src/*.rs`
  - `infra/prometheus/prometheus.yml`
  - `infra/grafana/dashboards/tryops-service-overview.json`
  - `src/tryops/dashboards.py`
  - `tests/test_dashboards.py`
- Outcome: the compiled Axum gateway exposes `GET /metrics` with Prometheus text for request
  counters, latency histogram buckets, quota decisions, rate-limit rejects, upstream proxy errors,
  and in-flight proxy requests. Prometheus now scrapes `gateway:8081`, and the service overview
  dashboard includes gateway request-rate, p95-latency, and rejection/error panels.
- Notes: this closes the live native gateway scrape path. Alertmanager routing is now wired by
  EXP-081; full P5 remains partial until the in-app dashboard, audit-log UI, external notification
  credentials, and full gateway-to-API trace stitching are done.

## EXP-044: Product Backend Route Registration

- Command: `PYTHONPATH=src python -m unittest tests.test_api_surface`
- Workload: Production product backend
- Evidence files:
  - `src/tryops/api.py`
  - `src/tryops/db.py`
  - `tests/test_api_surface.py`
  - `tests/test_api_v1_p2.py`
- Outcome: moves the product BFF routes before `create_app()` returns, imports the scoped API-key
  authenticator used by those routes, removes duplicate promotion-auth checks, and verifies the
  registered history, request detail, feedback, dashboard, model list, model promotion, and lineage
  endpoints against an isolated SQLite database.
- Notes: this closes P2 backend evidence. P3 remains open until the React console is built and served.

## EXP-045: Rust Gateway Edge Guardrail Enforcement

- Command: `make native-edge-guardrail-smoke`
- Workload: Production edge safety
- Evidence files:
  - `native/rust/tryops-gateway/src/*.rs`
  - `native/go/tryops-guardrail/*.go`
  - `docker-compose.yml`
  - `Makefile`
- Outcome: the Rust gateway calls the native Go guardrail sidecar before proxying
  `/api/llm/generate` when `TRYOPS_GATEWAY_GUARDRAIL_URL` is configured. A prompt-injection and
  system-prompt leakage request is rejected at the gateway with HTTP 403, `tryops.gateway_edge_guardrail.v1`,
  OWASP `LLM01:2025`/`LLM07:2025` evidence, and `tryops_gateway_guardrail_decisions_total`.
- Notes: this closes PA057 edge guardrails. Output-safety egress scanning still remains in the API
  generation path because the gateway cannot inspect model output before the upstream response exists.

## EXP-046: Modular Rust Gateway Boundary

- Command: `cargo test` and `make smoke`
- Workload: Native production edge maintainability
- Evidence files:
  - `native/rust/tryops-gateway/src/main.rs`
  - `native/rust/tryops-gateway/src/handlers.rs`
  - `native/rust/tryops-gateway/src/proxy.rs`
  - `native/rust/tryops-gateway/src/trace_context.rs`
  - `native/rust/tryops-gateway/src/guardrail.rs`
  - `native/rust/tryops-gateway/src/quota.rs`
  - `native/rust/tryops-gateway/src/quota_store.rs`
  - `native/rust/tryops-gateway/src/rate_limit.rs`
  - `native/rust/tryops-gateway/src/metrics.rs`
  - `native/rust/tryops-gateway/src/state.rs`
  - `native/rust/tryops-gateway/src/config.rs`
  - `native/rust/tryops-gateway/src/errors.rs`
  - `native/rust/tryops-gateway/src/cli.rs`
- Outcome: replaces the one-file Rust gateway with a 13-file Axum crate while preserving the same
  health, metrics, quota, reverse-proxy, signed-admin preflight, rate-limit, trace propagation, and
  Go-sidecar edge guardrail behavior.
- Notes: 16 Rust unit tests pass after the split, trace-context module, and durable quota store addition;
  `make native-rust-smoke` verifies `/api/health` proxying plus response `traceparent`/trace-id headers.

## EXP-047: Native Rust Durable Quota Ledger

- Command: `make native-quota-ledger-smoke`
- Workload: Enterprise quota durability
- Evidence files:
  - `native/rust/tryops-gateway/src/quota_store.rs`
  - `native/rust/tryops-gateway/src/quota_durable.rs`
  - `native/rust/tryops-gateway/src/quota_snapshot.rs`
  - `artifacts/eval/quota/native_quota_ledger.json`
  - `artifacts/eval/quota/native_quota_ledger_smoke.json`
  - `Makefile`
- Outcome: `TRYOPS_GATEWAY_QUOTA_LEDGER_PATH` makes the Rust gateway and `quota-check` CLI load and
  persist quota usage as `tryops.quota_ledger_file.v1`; the smoke runs the CLI twice in separate
  processes and verifies the ledger records two LLM requests, 600 estimated tokens, and a hashed
  tenant snapshot with `total_used=602`.
- Notes: the Rust gateway now also supports optional Postgres `tryops_quota_usage` upsert mirroring
  through `TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN` and Valkey-compatible RESP `INCRBY`/`EXPIRE` counter
  mirroring through `TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR`. Distributed multi-gateway atomic admission
  and restore drills remain production validation work.

## EXP-048: Native Go And C++ Module Split

- Command: `make native-go-build native-go-test native-go-smoke native-guardrail-build native-guardrail-test native-guardrail-smoke native-semantic-cache-build native-semantic-cache-test native-cpp-test`
- Workload: Native production code structure
- Evidence files:
  - `native/go/tryops-controller/main.go`
  - `native/go/tryops-controller/server.go`
  - `native/go/tryops-controller/handlers.go`
  - `native/go/tryops-controller/signature.go`
  - `native/go/tryops-controller/promotion.go`
  - `native/go/tryops-controller/fields.go`
  - `native/go/tryops-controller/types.go`
  - `native/go/tryops-guardrail/main.go`
  - `native/go/tryops-guardrail/server.go`
  - `native/go/tryops-guardrail/cli.go`
  - `native/go/tryops-guardrail/evaluator.go`
  - `native/go/tryops-guardrail/metrics.go`
  - `native/go/tryops-guardrail/types.go`
  - `native/cpp/tryops_semantic_cache/include/tryops_semantic_cache.hpp`
  - `native/cpp/tryops_semantic_cache/src/tryops_semantic_cache.cpp`
  - `native/cpp/tryops_semantic_cache/src/tryops_semantic_cache_cli.cpp`
  - `native/cpp/tryops_semantic_cache/tests/test_semantic_cache.cpp`
  - `Makefile`
- Outcome: the Go controller is split into server, handlers, signatures, promotion logic, helpers,
  and contracts; the Go guardrail is split into sidecar server, CLI, evaluator, metrics, and
  contracts; the C++ semantic-cache hot path is split into reusable core API/source, thin CLI, and
  native test.
- Notes: this directly reduces monolithic native entrypoints without adding Python to production
  paths. Verified with Go unit tests/smokes, C++ semantic-cache native test, and the existing native
  C++ policy test.

## EXP-049: Native Go Gateway Benchmark Driver

- Command: `make gateway-benchmark-native`
- Workload: Native production boundary throughput
- Evidence files:
  - `native/go/tryops-benchmark/main.go`
  - `native/go/tryops-benchmark/benchmark.go`
  - `native/go/tryops-benchmark/process.go`
  - `native/go/tryops-benchmark/loadgen.go`
  - `native/go/tryops-benchmark/loadgen_test.go`
  - `native/go/tryops-benchmark/payloads.go`
  - `native/go/tryops-benchmark/report.go`
  - `native/go/tryops-benchmark/types.go`
  - `artifacts/native/tryops_benchmark`
  - `artifacts/eval/gateway_benchmark/native_gateway_benchmark.json`
  - `Makefile`
- Outcome: replaces the Python/GIL-bound benchmark driver with a dependency-free Go stdlib load
  generator and records `tryops.native_gateway_benchmark.v1` evidence for three scenarios: identical
  `/health`, direct validated promotion POST, and full edge promotion POST through the Rust gateway
  into FastAPI.
- Notes: the Go driver measured the Rust gateway at 24,840.8 req/s on `/health` and 22,261.1 req/s
  on direct validated promotion preflight. The edge proxy path measured 698.8 req/s vs 759.0 req/s
  for FastAPI direct, which is the explicit cost of putting signed-artifact preflight and proxying in
  front of the same Python policy route.

## EXP-050: TryOps Console And Native Static Gateway

- Command: `npm run build`; `$HOME/.cargo/bin/cargo test`; `make native-static-smoke`
- Workload: Production Console shell and native static delivery
- Evidence files:
  - `web/package.json`
  - `web/package-lock.json`
  - `web/src/App.tsx`
  - `web/src/api.ts`
  - `web/src/components/AppShell.tsx`
  - `web/src/components/LlmPlayground.tsx`
  - `web/src/components/VtonStudio.tsx`
  - `web/src/components/DashboardView.tsx`
  - `web/src/components/HistoryView.tsx`
  - `web/src/components/RegistryView.tsx`
  - `web/src/components/GovernanceView.tsx`
  - `web/src/components/IncidentView.tsx`
  - `web/src/styles.css`
  - `native/rust/tryops-gateway/src/static_assets.rs`
  - `Dockerfile.gateway`
  - `docker-compose.yml`
  - `Makefile`
- Outcome: the repository now has a real browser Console shell backed by the existing API contracts,
  plus a Rust gateway static-serving profile that serves `web/dist`, applies SPA fallback for deep
  links, and keeps `/api/*` proxy routes intact.
- Notes: `npm audit` reports zero vulnerabilities after upgrading to Vite 8. `make native-static-smoke`
  proves the compiled gateway can serve `/`, return the SPA for `/console/history`, and still proxy
  `/api/health` through the native edge path.

## EXP-051: Native Go Full-Stack Compose Smoke

- Command: `make app-smoke`
- Workload: Local enterprise stack startup
- Evidence files:
  - `native/go/tryops-stack-smoke/main.go`
  - `native/go/tryops-stack-smoke/config.go`
  - `native/go/tryops-stack-smoke/scenarios.go`
  - `native/go/tryops-stack-smoke/httpcheck.go`
  - `native/go/tryops-stack-smoke/report.go`
  - `native/go/tryops-stack-smoke/types.go`
  - `native/go/tryops-stack-smoke/httpcheck_test.go`
  - `Dockerfile.mlflow`
  - `docker-compose.yml`
  - `Makefile`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
- Outcome: `make app-smoke` now starts the Compose stack on isolated host ports and runs a native
  Go readiness probe across the Console, SPA fallback, gateway-to-API health/readiness, LLM
  generation, gateway metrics, guardrail, Prometheus, Grafana, MinIO, and MLflow.
- Notes: the first run exposed two real production issues: fixed host ports can collide with local
  services, and the upstream MLflow image lacked the PostgreSQL driver. Compose ports are now
  overrideable, `app-smoke` uses a high isolated port range, Postgres has a healthcheck, and
  `Dockerfile.mlflow` installs `psycopg2-binary` plus `boto3`.

## EXP-052: Native Go Professor Demo Acceptance

- Command: `make professor-demo-acceptance`
- Workload: Final professor demo evidence gate
- Evidence files:
  - `native/go/tryops-demo-acceptance/main.go`
  - `native/go/tryops-demo-acceptance/config.go`
  - `native/go/tryops-demo-acceptance/commands.go`
  - `native/go/tryops-demo-acceptance/evidence.go`
  - `native/go/tryops-demo-acceptance/jsonutil.go`
  - `native/go/tryops-demo-acceptance/report.go`
  - `native/go/tryops-demo-acceptance/types.go`
  - `native/go/tryops-demo-acceptance/commands_test.go`
  - `native/go/tryops-demo-acceptance/evidence_test.go`
  - `artifacts/eval/demo_acceptance/professor_demo_acceptance.json`
  - `Makefile`
- Outcome: the acceptance target builds a split-file native Go checker, runs the bad-candidate
  promotion gate live with the expected blocked exit code, and validates seeded demo evidence for
  LLM Pareto, energy/carbon gate, full-stack Console/services, VTON comparison, promotion lineage,
  approved good-candidate promotion, rollback, and governance mapping.
- Notes: `professor-demo-refresh-acceptance` can rerun the heavier artifact-producing commands and
  `app-smoke` before validation. The default target is intentionally fast enough for final demo
  rehearsal while still checking the real policy-blocking moment live.

## EXP-053: Native Go Vulnerability Scan Runner

- Command: `make vulnerability-scan-sample`
- Workload: Installed-tool vulnerability scanning
- Evidence files:
  - `native/go/tryops-vuln-scan/main.go`
  - `native/go/tryops-vuln-scan/config.go`
  - `native/go/tryops-vuln-scan/tools.go`
  - `native/go/tryops-vuln-scan/npm.go`
  - `native/go/tryops-vuln-scan/report.go`
  - `native/go/tryops-vuln-scan/types.go`
  - `native/go/tryops-vuln-scan/npm_test.go`
  - `artifacts/eval/security/vulnerability_scan_report.json`
  - `artifacts/eval/security/npm_audit_web.json`
  - `Makefile`
- Outcome: the native scanner runner executed the available `npm audit` scanner for the Console
  package and reported 0 info/low/moderate/high/critical vulnerabilities.
- Notes: the report intentionally sets `coverage_level=partial` and `production_ready=false` because
  Trivy, Syft, Grype, pip-audit, gitleaks, osv-scanner, and Cosign are not installed. Missing tools
  are evidence gaps, not passes.

## EXP-054: Native Go Evaluation Index And Console Viewer

- Command: `make evaluation-index-sample`; `make app-smoke`
- Workload: Console evaluation evidence viewer
- Evidence files:
  - `native/go/tryops-evaluation-index/main.go`
  - `native/go/tryops-evaluation-index/discover.go`
  - `native/go/tryops-evaluation-index/classify.go`
  - `native/go/tryops-evaluation-index/summary.go`
  - `native/go/tryops-evaluation-index/index.go`
  - `native/go/tryops-evaluation-index/index_test.go`
  - `src/tryops/evaluation_artifacts.py`
  - `web/src/components/EvaluationView.tsx`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
  - `docker-compose.yml`
  - `Dockerfile.api`
  - `Makefile`
- Outcome: a split-file native Go indexer scans `artifacts/eval/**` and `reports/generated/**`,
  classifies 74 JSON evidence artifacts, and highlights Pareto, energy, VTON comparison, drift,
  full-stack smoke, professor-demo acceptance, and vulnerability-scan coverage. The API serves the
  generated index through `/api/evaluations/summary`, and the React Console renders an Evaluation
  page with summary tiles, highlights, category filtering, and report paths.
- Notes: adding the endpoint to `app-smoke` exposed that the API Docker image did not include
  `configs/api_keys.json`; `Dockerfile.api` now copies `configs/`, and Compose mounts the generated
  evaluation index read-only into the API container. The final `make app-smoke` passed the
  evaluation-summary check through the Rust gateway.

## EXP-055: VTON Comparison Artifact Serving And Console Gallery

- Command: `PYTHONPATH=src python -m unittest discover -s tests`; `cd web && npm run typecheck`;
  `cd web && npm run build`; `make native-rust-test`; `make native-stack-smoke-test`;
  `docker compose config`; `make app-smoke`
- Workload: Persisted VTON comparison UI and artifact-serving path
- Evidence files:
  - `src/tryops/artifacts.py`
  - `src/tryops/api.py`
  - `native/rust/tryops-gateway/src/proxy.rs`
  - `native/rust/tryops-gateway/src/handlers.rs`
  - `native/go/tryops-stack-smoke/scenarios.go`
  - `web/src/api.ts`
  - `web/src/types.ts`
  - `web/src/components/VtonStudio.tsx`
  - `web/src/styles.css`
  - `docker-compose.yml`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
- Outcome: the API serves `tryops.vton_comparison.v1` through `/api/vton/comparison` and safely
  serves allowed PNG/JSON artifacts through `/api/artifacts/file`; the Rust gateway rejects unsafe
  artifact paths before proxying; the Console renders person, garment, and baseline/candidate output
  images with latency, garment proxy score, SSIM, and failure labels.
- Notes: the first full-stack run exposed that mounting all of `artifacts/` read-only broke API trace
  emission. Compose now mounts evidence/demo/report inputs read-only and keeps `artifacts/runtime`,
  `artifacts/traces`, and `artifacts/logs` writable. The final `make app-smoke` passed 14 checks,
  including `vton_comparison_through_gateway` and `vton_artifact_image_through_gateway`; a direct PNG
  byte check returned `89504e470d0a1a0a`.

## EXP-056: Console Bad-Candidate Promotion Gate Drill

- Command: `cd web && npm run typecheck`; `cd web && npm run build`; `make native-stack-smoke-test`;
  `make app-smoke`
- Workload: Browser Incident drill for blocking an unsafe model candidate through the native edge
- Evidence files:
  - `web/src/components/IncidentView.tsx`
  - `web/src/api.ts`
  - `web/src/data.ts`
  - `web/src/types.ts`
  - `web/src/styles.css`
  - `native/go/tryops-stack-smoke/scenarios.go`
  - `native/go/tryops-stack-smoke/httpcheck.go`
  - `native/go/tryops-stack-smoke/types.go`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
- Outcome: the Incident Console now has a "Block bad model" action that submits the seeded bad VTON
  candidate to `/api/promotion/evaluate` with the Rust gateway signed-artifact preflight header. The
  response renders `approved=false`, the `risk_reviewer` actor, vulnerability/signature/provenance
  rejection reasons, and policy metadata on screen.
- Notes: the native Go full-stack smoke checker now includes `bad_candidate_gate_through_gateway`;
  the final `make app-smoke` passed 15 checks through the Rust gateway. This closes the K026
  professor-demo UI requirement while leaving alert routing and rollback click-actions tracked under
  the broader incident workflow.

## EXP-057: Console Rollback Drill Artifact Path

- Command: `PYTHONPATH=src python -m unittest tests.test_api_surface.ApiSurfaceTests.test_deployment_rollback_artifact_is_allowlisted_json tests.test_api_surface.ApiSurfaceTests.test_artifact_file_route_rejects_path_traversal`;
  `cd web && npm run typecheck`; `cd web && npm run build`; `cd native/go/tryops-stack-smoke && go test ./...`;
  `docker compose config`; `make app-smoke`
- Workload: Browser Incident rollback drill backed by deployment rollback evidence
- Evidence files:
  - `web/src/components/IncidentView.tsx`
  - `web/src/api.ts`
  - `web/src/data.ts`
  - `web/src/types.ts`
  - `src/tryops/artifacts.py`
  - `native/rust/tryops-gateway/src/proxy.rs`
  - `native/go/tryops-stack-smoke/scenarios.go`
  - `docker-compose.yml`
  - `tests/test_api_surface.py`
  - `artifacts/deployments/rollback_state.json`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
- Outcome: the Incident Console now includes a "Run rollback" action that loads
  `tryops.rollback_state.v1` and renders the latest `tryops.rollback_record.v1`, restored candidate,
  rolled-back candidate, package, profile, timestamp, reason, and triggering chaos scenarios.
- Notes: deployment JSON artifacts are now explicitly allowlisted in both the API resolver and Rust
  gateway artifact preflight, while traversal and unsupported-extension rejection remain enforced.
  The final `make app-smoke` passed 16 checks, including `rollback_state_artifact_through_gateway`.

## EXP-058: Native Pipeline Run Index And Console Runs View

- Command: `cd native/go/tryops-evaluation-index && go test ./...`;
  `cd native/go/tryops-stack-smoke && go test ./...`; `cd web && npm run typecheck`;
  `cd web && npm run build`; `make evaluation-index-sample`; `make app-smoke`
- Workload: Pipeline run history page backed by run-context, OpenLineage, and lineage artifacts
- Evidence files:
  - `native/go/tryops-evaluation-index/runs.go`
  - `native/go/tryops-evaluation-index/index.go`
  - `native/go/tryops-evaluation-index/types.go`
  - `native/go/tryops-evaluation-index/index_test.go`
  - `web/src/components/PipelineRunsView.tsx`
  - `web/src/App.tsx`
  - `web/src/data.ts`
  - `web/src/types.ts`
  - `web/src/styles.css`
  - `native/go/tryops-stack-smoke/scenarios.go`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
- Outcome: the native Go evaluation indexer now emits a `pipeline_runs` ledger by combining
  `run_context.json`, `openlineage_run_event.json`, and `lineage.json`. The Console has a Runs page
  that renders run ID, event type/time, candidate, workload, model, dataset, trace, signature state,
  and evidence paths.
- Notes: `make app-smoke` verifies the ledger through `/api/evaluations/summary` behind the Rust
  gateway by requiring `pipeline_runs`, `run-vton-001`, and `COMPLETE` in the response. This closes
  K009 without adding a Python-only run-history route.

## EXP-059: Native Optimization Panel And Console Sustainability View

- Command: `cd native/go/tryops-evaluation-index && gofmt -w *.go && go test ./...`;
  `cd native/go/tryops-stack-smoke && gofmt -w scenarios.go && go test ./...`;
  `cd web && npm run typecheck`; `cd web && npm run build`; `make evaluation-index-sample`;
  `make app-smoke`
- Workload: Operator-facing LLM optimization decision panel backed by native-indexed Pareto,
  leaderboard, and energy evidence
- Evidence files:
  - `native/go/tryops-evaluation-index/optimization.go`
  - `native/go/tryops-evaluation-index/types.go`
  - `native/go/tryops-evaluation-index/index.go`
  - `native/go/tryops-evaluation-index/index_test.go`
  - `native/go/tryops-stack-smoke/scenarios.go`
  - `web/src/components/EvaluationView.tsx`
  - `web/src/types.ts`
  - `web/src/styles.css`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
- Outcome: the native Go evaluation indexer now emits `optimization_panel` by joining
  `artifacts/eval/llm_pareto/pareto.json`, `artifacts/eval/leaderboard/leaderboard.json`, and
  `artifacts/eval/energy/energy_sweep.json`. The Console Evaluation view renders the recommended
  variant, judge backend, carbon-gate verdict, greenest variant, interactive quality-vs-latency
  frontier, per-variant VRAM/energy/SCI, and SLO gate.
- Notes: `make app-smoke` verifies the panel through `/api/evaluations/summary` behind the Rust
  gateway by requiring `optimization_panel`, `recommended_variant="4bit"`, and
  `carbon_gate_verdict="pass"`. This closes N008, K024, and K025 without adding a Python-only
  optimization route.

## EXP-060: Rust Gateway Auth Preflight

- Command: `docker compose build gateway`; `cd native/go/tryops-stack-smoke && go test ./...`;
  `docker compose config`; `make app-smoke`
- Workload: Native edge authorization for protected Console/API routes before FastAPI
- Evidence files:
  - `native/rust/tryops-gateway/src/auth.rs`
  - `native/rust/tryops-gateway/src/handlers.rs`
  - `native/rust/tryops-gateway/src/metrics.rs`
  - `native/rust/tryops-gateway/src/state.rs`
  - `native/rust/tryops-gateway/src/main.rs`
  - `native/go/tryops-stack-smoke/scenarios.go`
  - `configs/api_keys.json`
  - `Dockerfile.gateway`
  - `docker-compose.yml`
  - `Makefile`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
- Outcome: the Rust gateway now loads the hashed API-key registry, enforces required scopes for
  protected proxy routes, accepts API keys from query/header/body, optionally verifies HS256 bearer
  JWTs when `TRYOPS_GATEWAY_JWT_HS256_SECRET` is set, forwards non-secret principal metadata to the
  BFF, and exposes `tryops_gateway_auth_decisions_total`.
- Notes: `make app-smoke` now passes 18 checks, including missing-key rejection with HTTP 401,
  missing-scope rejection with HTTP 403, and gateway metrics containing the auth-decision counter.
  Host `cargo` is not installed in this workspace, so Rust validation used the Docker gateway build
  path; the image compiled successfully and includes `/opt/tryops/configs/api_keys.json`.

## EXP-061: Native Go VTON/LLM Job Runner

- Command: `cd native/go/tryops-job-runner && go test ./...`; `make native-job-runner-build`;
  `make native-job-runner-test`; `make native-job-runner-sample`; `cd native/go/tryops-evaluation-index && go test ./...`;
  `make evaluation-index-sample`; `make app-smoke`
- Workload: Native background-style runner for LLM and async VTON jobs through the Rust gateway
- Evidence files:
  - `native/go/tryops-job-runner/config.go`
  - `native/go/tryops-job-runner/payloads.go`
  - `native/go/tryops-job-runner/http.go`
  - `native/go/tryops-job-runner/retry.go`
  - `native/go/tryops-job-runner/runner.go`
  - `native/go/tryops-job-runner/response_summary.go`
  - `native/go/tryops-job-runner/report.go`
  - `native/go/tryops-job-runner/assets.go`
  - `native/go/tryops-job-runner/runner_test.go`
  - `native/go/tryops-evaluation-index/classify.go`
  - `native/go/tryops-evaluation-index/summary.go`
  - `artifacts/eval/jobs/native_job_runner_report.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
  - `artifacts/eval/full_stack/full_stack_smoke.json`
- Outcome: `tryops_job_runner` submits a direct LLM generation and an async VTON job through the Rust
  gateway, binds every HTTP attempt to a Go `context` deadline, retries transient submission failures,
  polls VTON job status until completion/failure, and emits compact operational evidence containing
  request IDs, trace IDs, quota verdicts, HTTP status, attempts, polls, and output paths.
- Notes: `make native-job-runner-sample` passed with 2/2 jobs. The VTON job completed after 2 polls.
  `make app-smoke` now builds and runs the job runner after the stack readiness probe, then refreshes
  the evaluation index so the Console evidence registry lists `Native Go job runner` under acceptance
  evidence.

## EXP-062: Native Go SLO Regression Gate

- Command: `cd native/go/tryops-slo-gate && go test ./...`; `make native-slo-gate-build`;
  `make native-slo-gate-test`; `make native-slo-gate-sample`;
  `cd native/go/tryops-evaluation-index && go test ./...`; `make evaluation-index-sample`
- Workload: CI-style SLO regression gate over the native Rust gateway benchmark artifact
- Evidence files:
  - `native/go/tryops-slo-gate/config.go`
  - `native/go/tryops-slo-gate/load.go`
  - `native/go/tryops-slo-gate/policy.go`
  - `native/go/tryops-slo-gate/gate.go`
  - `native/go/tryops-slo-gate/report.go`
  - `native/go/tryops-slo-gate/types.go`
  - `native/go/tryops-slo-gate/gate_test.go`
  - `native/go/tryops-evaluation-index/classify.go`
  - `native/go/tryops-evaluation-index/summary.go`
  - `artifacts/eval/gateway_benchmark/native_gateway_benchmark.json`
  - `artifacts/eval/slo/native_slo_gate_report.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: `tryops_slo_gate` consumes `tryops.native_gateway_benchmark.v1`, applies explicit
  error-rate, p95/p99 latency, throughput, speedup, and edge-overhead rules, writes
  `tryops.native_slo_gate.v1`, and exits nonzero if any rule fails.
- Notes: current local evidence passes 3/3 rules: gateway health native latency, direct promotion
  native latency, and edge-proxy overhead. The evaluation index now lists `Native SLO regression gate`
  as monitoring evidence.

## EXP-063: Native Go Audit/Webhook Event Dispatcher

- Command: `cd native/go/tryops-event-dispatcher && go test ./...`;
  `make native-event-dispatcher-build`; `make native-event-dispatcher-test`;
  `make native-event-dispatcher-sample`; `cd native/go/tryops-evaluation-index && go test ./...`;
  `make evaluation-index-sample`
- Workload: Native audit and signed-webhook fanout for promotion, feedback, incident, and quota events
- Evidence files:
  - `native/go/tryops-event-dispatcher/config.go`
  - `native/go/tryops-event-dispatcher/events.go`
  - `native/go/tryops-event-dispatcher/load.go`
  - `native/go/tryops-event-dispatcher/audit.go`
  - `native/go/tryops-event-dispatcher/signature.go`
  - `native/go/tryops-event-dispatcher/webhook.go`
  - `native/go/tryops-event-dispatcher/sample.go`
  - `native/go/tryops-event-dispatcher/dispatcher.go`
  - `native/go/tryops-event-dispatcher/report.go`
  - `native/go/tryops-event-dispatcher/types.go`
  - `native/go/tryops-event-dispatcher/dispatcher_test.go`
  - `native/go/tryops-evaluation-index/classify.go`
  - `native/go/tryops-evaluation-index/summary.go`
  - `artifacts/eval/events/native_event_dispatcher_report.json`
  - `artifacts/eval/events/native_audit_events.jsonl`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: `tryops_event_dispatcher` validates CloudEvents-style event envelopes, writes
  `tryops.native_audit_event.v1` JSONL audit records, signs webhook payloads with HMAC-SHA256,
  retries transient delivery failures, and emits `tryops.native_event_dispatcher.v1`.
- Notes: `make native-event-dispatcher-sample` passed with 4/4 events: promotion, feedback,
  incident, and quota. The local signed receiver accepted all four webhook deliveries and the
  evaluation index lists `Native event dispatcher` under governance evidence.

## EXP-064: Console Professor Demo Mode

- Command: `cd native/go/tryops-demo-acceptance && go test ./...`; `cd web && npm run typecheck`;
  `cd web && npm run build`; `make professor-demo-acceptance`
- Workload: Guided offline Console walkthrough backed by seeded local evidence
- Evidence files:
  - `web/src/components/ProfessorDemoView.tsx`
  - `web/src/data.ts`
  - `web/src/App.tsx`
  - `web/src/types.ts`
  - `web/src/styles.css`
  - `native/go/tryops-demo-acceptance/evidence.go`
  - `native/go/tryops-demo-acceptance/evidence_test.go`
  - `artifacts/eval/demo_acceptance/professor_demo_acceptance.json`
- Outcome: the React Console now has a `Professor Demo` nav entry with a seven-step, seeded,
  no-network/no-GPU walkthrough covering stack preflight, native quota admission, bad-model blocking,
  LLM Pareto/energy optimization, VTON comparison, signed lineage/promotion, rollback, and governance.
  The native Go acceptance harness validates the quota ledger and verifies the demo view plus seeded
  data source contract in addition to existing artifact checks.
- Notes: `make professor-demo-acceptance` passed with 12/12 checks: one live blocked bad-candidate
  command and 11 evidence/source validations.

## EXP-065: Native Go Professor Demo Backup Video

- Command: `cd native/go/tryops-demo-recorder && go test ./...`; `make professor-demo-video`;
  `ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,avg_frame_rate -of json artifacts/demo/professor_demo_video/professor_demo_backup.mp4`;
  `make evaluation-index-sample`; `cd web && npm run build`
- Workload: Offline backup recording for the Console professor demo path
- Evidence files:
  - `web/src/professor_demo_storyboard.json`
  - `web/src/data.ts`
  - `native/go/tryops-demo-recorder/config.go`
  - `native/go/tryops-demo-recorder/storyboard.go`
  - `native/go/tryops-demo-recorder/render.go`
  - `native/go/tryops-demo-recorder/encoder.go`
  - `native/go/tryops-demo-recorder/report.go`
  - `native/go/tryops-demo-recorder/recorder_test.go`
  - `artifacts/demo/professor_demo_video/professor_demo_backup.mp4`
  - `artifacts/demo/professor_demo_video/frames/frame_001.png`
  - `artifacts/eval/demo_video/professor_demo_video.json`
- Outcome: `tryops_demo_recorder` loads the same JSON storyboard used by the React Console, renders
  intro/step/close frames with Go image primitives and system fonts, invokes FFmpeg to encode an
  H.264 MP4, and emits `tryops.professor_demo_video.v1` with frame count, duration, dimensions,
  encoder command, byte size, and SHA-256.
- Notes: the generated backup video is 1280x720, 30 FPS, 18.0 seconds, 9 frames, and 390,360 bytes.
  Visual inspection of the optimization frame confirmed the corrected layout has no overlap and no
  clipped narration.

## EXP-066: Go Controller Re-Runs Native C++ Promotion Policy

- Command: `make native-go-test`; `make native-cpp-test`; `make registry-webhook-sample`;
  `PYTHONPATH=src python -m unittest discover -s tests`
- Workload: Native Go/C++ deployment-control-plane enforcement for signed registry webhooks
- Evidence files:
  - `native/go/tryops-controller/policy_candidate.go`
  - `native/go/tryops-controller/policy_wire.go`
  - `native/go/tryops-controller/policy_client.go`
  - `native/go/tryops-controller/policy_gate.go`
  - `native/go/tryops-controller/policy_types.go`
  - `native/go/tryops-controller/policy_test.go`
  - `native/cpp/tryops_policy/src/tryops_policy.cpp`
  - `native/cpp/tryops_policy/src/tryops_policy_cli.cpp`
  - `reports/generated/vton-catvton-2026-06-11-001/policy_candidate.json`
  - `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/deployment_manifest.json`
  - `artifacts/eval/registry_webhook/registry_webhook_report.json`
- Outcome: signed registry webhooks now include `policy_candidate`; when
  `TRYOPS_CONTROLLER_POLICY_CLI` is set, the Go controller renders the same key/value wire payload
  used by the Python bridge, executes `tryops_policy_cli`, accepts exit `0` as approval and exit `2`
  as a policy rejection, and only emits GitOps/canary actions when the C++ decision approves.
- Notes: `make registry-webhook-sample` returned HTTP 202 with
  `native_policy.available=true`, `wire_format=tryops.native_policy.v1`, and
  `decision.approved=true`. Go unit tests also cover native approval and native rejection through
  stub CLIs so the controller fails closed when the C++ verdict rejects a candidate.

## EXP-067: DVC + MinIO Data Versioning Verified

- Command: `DVC_NO_ANALYTICS=1 AWS_ACCESS_KEY_ID=tryops AWS_SECRET_ACCESS_KEY=tryops123 artifacts/tools/dvc-venv/bin/dvc repro`;
  `DVC_NO_ANALYTICS=1 AWS_ACCESS_KEY_ID=tryops AWS_SECRET_ACCESS_KEY=tryops123 artifacts/tools/dvc-venv/bin/dvc push`;
  `make native-data-versioning-test`; `make dvc-minio-sample`; `make evaluation-index-sample`
- Workload: Dataset and generated evidence versioning through DVC with MinIO remote storage
- Evidence files:
  - `.dvc/config`
  - `dvc.yaml`
  - `dvc.lock`
  - `native/go/tryops-data-versioning/config.go`
  - `native/go/tryops-data-versioning/dvc.go`
  - `native/go/tryops-data-versioning/s3sign.go`
  - `native/go/tryops-data-versioning/minio.go`
  - `native/go/tryops-data-versioning/report.go`
  - `native/go/tryops-data-versioning/verifier_test.go`
  - `artifacts/eval/data_versioning/dvc_minio_report.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: DVC 3.67.1 with S3 support runs from `artifacts/tools/dvc-venv`, `dvc repro` pins the
  promotion evidence stage in `dvc.lock`, and `dvc push` uploads the cache to the Compose MinIO
  bucket `tryops-artifacts` under prefix `dvc`.
- Notes: the native Go verifier avoids SDK dependencies and signs a ListObjectsV2 request directly
  with AWS Signature Version 4. It verified 12 local cache objects and 12 remote MinIO objects with
  matching total bytes, then wrote `tryops.dvc_minio_versioning.v1` with `passed=true`.

## EXP-068: Transformers CLIP Garment Similarity Verified

- Command: `PYTHONPATH=src python -m unittest tests.test_garment_similarity`;
  `make vton-clip-similarity-sample`; `make evaluation-index-sample`
- Workload: Neural garment-preservation similarity for the seeded VTON output
- Evidence files:
  - `src/tryops/pipelines/garment_similarity.py`
  - `scripts/evaluate_garment_similarity.py`
  - `artifacts/eval/vton_clip/garment_clip_similarity.json`
  - `native/go/tryops-evaluation-index/classify.go`
  - `native/go/tryops-evaluation-index/summary.go`
  - `native/go/tryops-evaluation-index/index.go`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: The local neural CLIP path uses Hugging Face Transformers CLIP when enabled with
  `TRYOPS_ENABLE_CLIP=1` or `--enable-clip`, computes image-image similarity between the source
  garment patch and generated output patch, and scores the candidate patch against text prompts.
  The seeded proof uses `openai/clip-vit-base-patch32` on CPU and writes
  `tryops.garment_similarity.v1` with `clip.available=true`.
- Notes: The deterministic patch proxy still runs by default for offline smoke tests. Production
  benchmark claims still require a fixed VTON set, pinned local model artifacts, and confidence
  intervals over CLIP/OpenCLIP scores.

## EXP-069: Rust Edge Semantic-Cache Admission And C++ Lookup

- Command: `make native-rust-test`; `make native-edge-cache-smoke`
- Workload: Native gateway cache-admission preflight and C++ cache lookup for LLM generation
- Evidence files:
  - `native/rust/tryops-gateway/src/semantic_cache.rs`
  - `native/rust/tryops-gateway/src/handlers.rs`
  - `native/rust/tryops-gateway/src/metrics.rs`
  - `native/cpp/tryops_semantic_cache/`
  - `Makefile`
- Outcome: The Rust gateway now evaluates `POST /api/llm/generate` before proxying to FastAPI,
  honors `semantic_cache_enabled`, rejects invalid or privacy-sensitive prompts from cache
  admission, hashes admitted cache keys, invokes the native C++ semantic-cache CLI when configured,
  forwards bounded `x-tryops-edge-cache-*` headers, and exports
  `tryops_gateway_semantic_cache_admissions_total` plus
  `tryops_gateway_semantic_cache_lookups_total`.
- Notes: `make native-edge-cache-smoke` intentionally uses the gateway as its own upstream so the
  proxied request returns the local static-method 405, while response headers and Prometheus metrics
  still prove the Rust-to-C++ edge path without starting Python.

## EXP-070: Native GGUF CPU Preflight

- Command: `make native-gguf-preflight-test`; `make llm-gguf-preflight-sample`; `make evaluation-index-sample`
- Workload: CPU-first LLM deployment preflight for GGUF artifacts
- Evidence files:
  - `native/cpp/tryops_gguf_preflight/include/tryops_gguf_preflight.hpp`
  - `native/cpp/tryops_gguf_preflight/src/tryops_gguf_preflight.cpp`
  - `native/cpp/tryops_gguf_preflight/src/tryops_gguf_preflight_cli.cpp`
  - `native/cpp/tryops_gguf_preflight/tests/test_gguf_preflight.cpp`
  - `artifacts/models/gguf/SmolLM2-135M-Instruct-Q2_K.gguf`
  - `artifacts/eval/llm_gguf/gguf_preflight.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the native C++ parser validates a real GGUF v3 artifact, records 88.2 MB,
  272 tensors, 37 metadata entries, `general.architecture=llama`, `mostly_q2_k`, context length
  8192, and tensor type counts for F32/IQ4_NL/Q3_K/Q8_0.
- Notes: this proves the artifact/header/metadata/tensor-inspection path and the evaluation
  contract. `llama-cli` is not installed here, so live llama.cpp generation and speed/quality
  claims remain future work.

## EXP-071: Native Go vLLM Serving Probe

- Command: `make native-vllm-probe-test`; `make native-vllm-probe-build`;
  `make llm-vllm-probe-sample`; `make evaluation-index-sample`
- Workload: vLLM OpenAI-compatible serving readiness and live benchmark harness
- Evidence files:
  - `native/go/tryops-vllm-probe/config.go`
  - `native/go/tryops-vllm-probe/environment.go`
  - `native/go/tryops-vllm-probe/http.go`
  - `native/go/tryops-vllm-probe/probe.go`
  - `native/go/tryops-vllm-probe/jsonutil.go`
  - `native/go/tryops-vllm-probe/latency.go`
  - `native/go/tryops-vllm-probe/report.go`
  - `native/go/tryops-vllm-probe/main.go`
  - `native/go/tryops-vllm-probe/probe_test.go`
  - `artifacts/eval/llm_vllm/vllm_serving_probe.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the native Go probe validates the OpenAI-compatible `/v1/models` and
  `/v1/chat/completions` contract against a test server, records GPU/runtime readiness locally, and
  is surfaced in the evaluation index as `llm_vllm`.
- Notes: the current real local artifact records NVIDIA L4 hardware but `status=skipped` because
  `vllm` is not installed and no vLLM endpoint is serving at `127.0.0.1:8000`. Live vLLM speed,
  quality, batching, and prefix-cache claims remain open until `vllm serve` is running.

## EXP-072: Native GPTQ/AWQ Model Preflight

- Command: `make native-quantized-preflight-test`; `make native-quantized-preflight-build`;
  `make llm-quantized-preflight-sample`; `make evaluation-index-sample`
- Workload: GPTQ/AWQ quantized-model candidate and runtime readiness
- Evidence files:
  - `native/go/tryops-quantized-preflight/config.go`
  - `native/go/tryops-quantized-preflight/runtime.go`
  - `native/go/tryops-quantized-preflight/hf.go`
  - `native/go/tryops-quantized-preflight/probe.go`
  - `native/go/tryops-quantized-preflight/jsonutil.go`
  - `native/go/tryops-quantized-preflight/report.go`
  - `native/go/tryops-quantized-preflight/main.go`
  - `native/go/tryops-quantized-preflight/probe_test.go`
  - `artifacts/eval/llm_quantized/quantized_model_preflight.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the native Go probe verifies suitable Apache-2.0 Qwen2.5-0.5B GPTQ-Int4 and AWQ
  repositories, parses `quantization_config` from `config.json`, checks SafeTensors reachability,
  detects the NVIDIA L4, and records the local package set.
- Notes: the current artifact is `status=partial`: GPTQ and AWQ candidates are suitable, but live
  loading is not attempted because `gptqmodel`/`auto_gptq` and `awq`/`autoawq` are absent. Live
  latency, memory, quality, and throughput claims remain open until loader runtimes are installed
  and generation benchmarks are run.

## EXP-073: Native Config Contract Drift Gate

- Command: `make native-config-contract-test`; `make native-config-contract-sample`;
  `make evaluation-index-sample`
- Workload: Native service/env/readiness contract validation
- Evidence files:
  - `native/go/tryops-config-contract/config.go`
  - `native/go/tryops-config-contract/compose.go`
  - `native/go/tryops-config-contract/contract.go`
  - `native/go/tryops-config-contract/evaluator.go`
  - `native/go/tryops-config-contract/secrets.go`
  - `native/go/tryops-config-contract/source.go`
  - `native/go/tryops-config-contract/report.go`
  - `native/go/tryops-config-contract/main.go`
  - `native/go/tryops-config-contract/evaluator_test.go`
  - `.env.example`
  - `docker-compose.yml`
  - `native/rust/tryops-gateway/src/quota_durable.rs`
  - `artifacts/eval/config/native_config_contract_report.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the native Go checker parses `docker-compose.yml`, verifies 10 enterprise services,
  required env vars, 4 Compose secrets, direct credential-env absence, `.env.example` coverage,
  port interpolations, healthchecks, dependency readiness conditions, named volumes, and Rust
  gateway source references for gateway env vars. The report passed all 111 current checks and is
  highlighted in the evaluation index as `config_contract`.
- Notes: this closes the local config drift gate and PA044 local secret-loading evidence. Production
  hardening still needs vault/workload-identity rotation, TLS, migration/pooling checks, and external
  CI enforcement around the same native contract.

## EXP-074: Native Performance Budget CI Gate

- Command: `make native-performance-budget-test`; `make native-performance-budget-sample`;
  `make evaluation-index-sample`
- Workload: Rust/Go/C++ native performance and CI evidence
- Evidence files:
  - `native/go/tryops-performance-budget/config.go`
  - `native/go/tryops-performance-budget/load.go`
  - `native/go/tryops-performance-budget/evaluator.go`
  - `native/go/tryops-performance-budget/markdown.go`
  - `native/go/tryops-performance-budget/main.go`
  - `native/go/tryops-performance-budget/evaluator_test.go`
  - `artifacts/eval/performance/native_performance_budget.json`
  - `artifacts/eval/performance/native_performance_budget.md`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the native Go gate evaluates 11 CI budget rows across Rust, Go, and C++ evidence:
  gateway p95/p99/RPS/speedup budgets, edge-proxy overhead, the Go SLO report, the Go config
  contract report, C++ perf-stat SLOs, and required executable native binaries.
- Notes: this closes PA085 locally. The generated Markdown is suitable for `GITHUB_STEP_SUMMARY`,
  while the JSON/Markdown pair should be uploaded as durable CI artifacts in the future workflow.

## EXP-075: Native C++ VTON API Execution Evidence

- Command: `make vton-native-api-sample`; `make evaluation-index-sample`
- Workload: VTON API/job execution and request-detail quality evidence
- Evidence files:
  - `src/tryops/vton_native_bridge.py`
  - `src/tryops/api.py`
  - `scripts/evaluate_vton_native_api.py`
  - `artifacts/eval/vton_native_api/vton_native_api_report.json`
  - `artifacts/eval/vton_native_api/api_output.png.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the FastAPI VTON endpoint surfaces C++ preprocessing and C++ image metrics as
  `tryops.native_vton_execution.v1`, persists the enriched sidecar report beside the output image,
  and stores the native quality score in the request row for dashboard/request detail rollups.
- Notes: this closes PA079 and PA081 for the local product path. The current quality metric is a
  deterministic native proxy (`dhash_similarity` over person vs output), not a claim of neural VTON
  perceptual quality.

## EXP-076: Native Trace/Log Envelope Contract

- Command: `make native-trace-envelope-sample`; `make native-evaluation-index-test`
- Workload: Cross-runtime trace/log envelope validation for Rust, Go, C++, and FastAPI
- Evidence files:
  - `contracts/native_trace_log_envelope.schema.json`
  - `src/tryops/trace_envelope.py`
  - `native/rust/tryops-gateway/src/trace_envelope.rs`
  - `native/cpp/tryops_trace_envelope/include/tryops_trace_envelope.hpp`
  - `native/cpp/tryops_trace_envelope/src/tryops_trace_envelope.cpp`
  - `native/cpp/tryops_trace_envelope/src/tryops_trace_envelope_cli.cpp`
  - `native/go/tryops-trace-envelope/`
  - `scripts/evaluate_native_trace_envelope.py`
  - `artifacts/eval/trace_envelope/native_trace_envelope_report.json`
- Outcome: the report passes 4/4 envelopes and covers Rust, Go, C++, and FastAPI using the same
  W3C Trace Context and OpenTelemetry log/resource field constraints.
- Notes: this closes PA082 for the local native contract. OpenTelemetry Collector wiring and
  trace/log correlation are now covered separately by EXP-080; live OTLP exporters under sustained
  load remain P5/PA051 production work.

## EXP-077: Native Container Image Split Contract

- Command: `make native-container-contract-sample`; `docker compose config`;
  `make native-go-test native-evaluation-index-test evaluation-index-sample`
- Workload: Split-image production container contract for gateway, controller, guardrail, benchmark,
  C++ tools, API, and web assets
- Evidence files:
  - `Dockerfile.controller`
  - `Dockerfile.benchmark`
  - `Dockerfile.cpp-tools`
  - `Dockerfile.web-assets`
  - `configs/container_images.json`
  - `native/go/tryops-container-contract/`
  - `artifacts/eval/containers/native_container_contract_report.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the native Go checker validates seven required image roles, matching Compose services,
  explicit Dockerfile/context wiring, source path coverage, multi-stage native builds, and non-SDK
  runtime stages. The report passes 87/87 checks and is highlighted by the evaluation index.
- Notes: this closes PA084 at the local contract level. CI should still build, scan, sign, and push
  the images with digest/provenance metadata before a production release.

## EXP-078: Native Quota Read Model And BFF Summary

- Command: `make native-quota-read-model-sample`;
  `make native-quota-read-model-test native-go-test native-evaluation-index-test evaluation-index-sample`;
  `python -m unittest tests/test_quota_read_model.py tests/test_api_surface.py`; `npm run typecheck`
- Workload: Native-first quota/accounting read model for tenant utilization, risk, and showback
- Evidence files:
  - `native/go/tryops-quota-read-model/`
  - `src/tryops/quota_read_model.py`
  - `src/tryops/api.py`
  - `web/src/api.ts`
  - `web/src/App.tsx`
  - `web/src/components/DashboardView.tsx`
  - `artifacts/eval/quota/native_quota_read_model.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the Go module consumes Rust gateway quota usage snapshots, emits
  `tryops.native_quota_read_model.v1` with hashed tenants, limits, utilization, native-source
  status, and showback, and the BFF exposes the same contract through `/api/quota/summary`.
  The Console Dashboard now shows tenant risk, used units, showback, and native ledger status.
- Notes: this closes PA086 for the local product path. Distributed multi-gateway atomic quota
  validation and restore drills remain P6/P8 production hardening work.

## EXP-079: Native Runtime Telemetry Exporter

- Command: `make native-runtime-telemetry-test`; `make native-runtime-telemetry-sample`;
  `make native-evaluation-index-test evaluation-index-sample`
- Workload: Native LLM throughput and GPU runtime telemetry evidence
- Evidence files:
  - `native/go/tryops-runtime-telemetry/`
  - `artifacts/eval/runtime/native_runtime_telemetry.json`
  - `artifacts/eval/runtime/native_runtime_telemetry.prom`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the split Go exporter reads LLM benchmark and Pareto artifacts, records benchmark
  tokens/sec, variant tokens/sec, peak VRAM values, native SLO stats, and live `nvidia-smi`
  snapshots for GPU memory/utilization/power. It emits both JSON and Prometheus text and is
  highlighted in the evaluation index as `runtime_telemetry`.
- Notes: this closes H007/H008 with native evidence. Per-request live VRAM/energy attribution
  remains part of the broader exporter and dashboard work.

## EXP-080: Native OpenTelemetry Collector And Correlation Contract

- Command: `make native-observability-contract-test`; `make native-observability-contract-sample`;
  `make native-evaluation-index-test evaluation-index-sample`
- Workload: OpenTelemetry Collector wiring, JSONL structured logs, and gateway/API trace correlation
- Evidence files:
  - `infra/otel/collector.yml`
  - `docker-compose.yml`
  - `infra/prometheus/prometheus.yml`
  - `native/rust/tryops-gateway/src/trace_envelope.rs`
  - `native/rust/tryops-gateway/src/handlers.rs`
  - `native/go/tryops-observability-contract/`
  - `artifacts/logs/gateway_events.jsonl`
  - `artifacts/eval/traces/api_spans.jsonl`
  - `artifacts/eval/traces/api_events.jsonl`
  - `artifacts/eval/observability/native_observability_contract.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the Collector config now includes OTLP gRPC/HTTP receivers, JSONL filelog ingestion,
  memory/resource/batch processors, trace/log/metric file exporters, and health checks. Compose runs
  `otel-collector`, Prometheus scrapes `otel-collector:8888`, the Rust gateway writes native JSONL
  envelopes when `TRYOPS_GATEWAY_STRUCTURED_LOG_PATH` is set, and the Go verifier passes 46/46
  checks across Collector, Compose, Prometheus, gateway logs, API spans, API logs, shared trace IDs,
  service names, model-call metadata, and sensitive-payload redaction.
- Notes: this moves PA051/PA052 to partial production coverage. Live OTLP SDK/exporter emission from
  every runtime and DB-backed log search remain production hardening work.

## EXP-081: Native Alertmanager Routing Contract

- Command: `make native-alertmanager-contract-test`; `make native-alertmanager-contract-sample`;
  `make native-go-test native-evaluation-index-test evaluation-index-sample`
- Workload: Prometheus alert routing and Alertmanager incident ingress
- Evidence files:
  - `infra/alertmanager/alertmanager.yml`
  - `infra/prometheus/prometheus.yml`
  - `infra/prometheus/tryops_alerts.yml`
  - `infra/prometheus/tryops_burn_rate_alerts.yml`
  - `infra/prometheus/tryops_finops_alerts.yml`
  - `docker-compose.yml`
  - `native/go/tryops-controller/handlers.go`
  - `native/go/tryops-controller/promotion.go`
  - `native/go/tryops-alertmanager-contract/`
  - `artifacts/eval/alerts/native_alertmanager_contract.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: Alertmanager now runs as a Compose service, Prometheus forwards alerts to
  `alertmanager:9093`, page alerts route to the Go controller `/alerts/webhook`, warning/ticket
  alerts use the local ticket receiver, and the native verifier passes 24/24 checks across routing,
  receivers, inhibition, Compose, Prometheus forwarding, and 16 alert rules.
- Notes: this closes PA053 for local open-source product evidence. External pager/chat/ticket
  credentials remain part of PA060 secret-management hardening.

## EXP-082: Native Postgres Migration And Pool Contract

- Command: `make native-db-migrator-test`; `make native-db-migrator-sample`;
  `TRYOPS_POSTGRES_MIGRATION_DSN=postgres://tryops:tryops@127.0.0.1:15432/tryops?sslmode=disable make native-db-migrator-apply`;
  `make native-evaluation-index-test evaluation-index-sample`
- Workload: Postgres schema migration and pooled connection evidence for enterprise persistence
  readiness
- Evidence files:
  - `infra/postgres/migrations/001_product_schema.sql`
  - `infra/postgres/migrations/002_quota_usage.sql`
  - `native/go/tryops-db-migrator/`
  - `artifacts/eval/postgres/native_postgres_migration.json`
  - `artifacts/eval/postgres/native_postgres_migration_live.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the native migrator validates two ordered SQL migrations, enforces required
  product/quota/schema-history tables, and reports 20/20 plan checks. A live apply against the
  Compose Postgres endpoint on `127.0.0.1:15432` passed 33/33 checks with `pgxpool` ping/acquire
  evidence, persisted both migrations in `tryops_schema_migrations`, verified live tables, and
  produced an idempotent second apply with both migrations reported as already applied.
- Notes: this closes PA058 local/native migration and pool evidence. PA006 remains partial because
  the application BFF still defaults to SQLite. Backup/restore is covered separately by EXP-083.

## EXP-083: Native Backup Restore Drill

- Command: `make native-backup-restore-test`; `make native-backup-restore-sample`;
  `TRYOPS_POSTGRES_BACKUP_DSN=postgres://tryops:tryops@127.0.0.1:15432/tryops?sslmode=disable make native-backup-restore-live`;
  `make native-evaluation-index-test evaluation-index-sample`
- Workload: Native Postgres and MinIO backup/restore drill for enterprise recovery readiness
- Evidence files:
  - `infra/backup/restore_drill.cron`
  - `native/go/tryops-backup-restore/`
  - `artifacts/backups/native_restore_drill/tryops-postgres-20260612T033017Z.dump`
  - `artifacts/eval/backup/native_backup_restore_drill.json`
  - `artifacts/eval/backup/native_backup_restore_live.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: plan mode passed 20/20 checks over Compose Postgres/MinIO storage, restore isolation,
  schedule wiring, and required tools. Live mode passed 50/50 checks, used the Postgres container's
  matching PG16 `pg_dump`/`pg_restore` tools to create a 42,609-byte custom dump, restored it into
  isolated database `tryops_restore_drill`, matched row counts for seven required tables, mirrored
  one MinIO object through `mc mirror` into `tryops-restore-drill`, and cleaned temporary restore
  targets.
- Notes: this closes PA059 local/native evidence. TLS termination is covered separately by EXP-084;
  the production profile still needs vault/workload identity rotation, scanner/signing CI, load
  testing, and incident workflow.

## EXP-084: Native TLS Termination Contract

- Command: `make native-rust-test`; `make native-rust-smoke`;
  `make native-tls-contract-test`; `make native-tls-contract-sample`; `make native-tls-smoke`;
  `make native-evaluation-index-test evaluation-index-sample`; `docker compose config`;
  `docker compose --profile tls config`
- Workload: Rust gateway HTTPS termination and Compose TLS profile validation
- Evidence files:
  - `native/rust/tryops-gateway/src/tls.rs`
  - `native/rust/tryops-gateway/src/cli.rs`
  - `native/go/tryops-tls-contract/`
  - `docker-compose.yml`
  - `.env.example`
  - `artifacts/tls/tryops.local.crt`
  - `artifacts/tls/tryops.local.key`
  - `artifacts/eval/tls/native_tls_contract.json`
  - `artifacts/eval/tls/native_tls_contract_live.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the Rust gateway now serves HTTPS through axum-server/rustls when
  `TRYOPS_GATEWAY_TLS_CERT_PATH` and `TRYOPS_GATEWAY_TLS_KEY_PATH` are set. Compose adds an optional
  `gateway-tls` profile on port 8443 with certificate and private-key material injected through
  `TRYOPS_TLS_CERT_PEM` and `TRYOPS_TLS_KEY_PEM` secrets. Plan mode passed 24/24 checks across
  Compose profile wiring, secret mounts, HTTPS healthcheck configuration, and local SAN certificate
  validation. Live smoke passed 30/30 checks with a TLS1.3 handshake, `TLS_AES_128_GCM_SHA256`,
  HTTPS `/health` status 200, one peer certificate, and plaintext HTTP rejection on the TLS port.
- Notes: this closes PA061 for local/native production-profile evidence. Real production deployment
  should replace the sample self-signed certificate with vault/workload-identity managed material
  under PA060.

## EXP-085: RBAC Session And Role-Aware Console Navigation

- Command: `PYTHONPATH=src python -m unittest tests.test_auth tests.test_api_surface`;
  `cargo test --manifest-path native/rust/tryops-gateway/Cargo.toml auth`; `npm run typecheck`
- Workload: Viewer/operator/admin route authorization and Console navigation enforcement
- Evidence files:
  - `configs/api_keys.json`
  - `src/tryops/auth.py`
  - `src/tryops/api.py`
  - `native/rust/tryops-gateway/src/auth.rs`
  - `web/src/App.tsx`
  - `web/src/api.ts`
  - `web/src/components/AppShell.tsx`
  - `web/src/data.ts`
  - `web/src/types.ts`
  - `tests/test_auth.py`
  - `tests/test_api_surface.py`
- Outcome: the local API-key registry now has active viewer, operator, and admin principals with
  `session:read`. FastAPI exposes `/api/auth/session` and `/v1/auth/session` as
  `tryops.rbac_session.v1`, including allowed Console navigation and permission booleans. The Rust
  gateway protects `/v1/auth/session` with native `session:read` preflight. The React shell filters
  navigation from the returned permission set, shows the active role, and promotion actions now use
  the active session key instead of a hard-coded privileged key.
- Notes: this closes PA055 for local product RBAC evidence. Production identity-provider federation
  and key rotation remain under PA060.

## EXP-086: Native Full-Stack Load SLO Gate

- Command: `make native-fullstack-load-test`; `make native-fullstack-load-sample`;
  `make native-evaluation-index-test evaluation-index-sample`
- Workload: Rust gateway plus FastAPI product BFF load/SLO validation
- Evidence files:
  - `native/go/tryops-fullstack-load/`
  - `native/go/tryops-evaluation-index/`
  - `artifacts/eval/load/native_fullstack_load.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the split Go driver starts the FastAPI BFF and Rust gateway, then drives six weighted
  product scenarios through `/api/*`: health, RBAC session, evaluation summary, quota summary, LLM
  generation, and operator promotion gate. The latest local run passed 6/6 scenarios with 504 total
  requests, zero errors, worst p95 39.965 ms, worst p99 47.056 ms, and minimum RPS 126.29.
- Notes: this partially completes PA064 with native Go full-stack load/SLO evidence. The report
  records `k6` and `locust` as unavailable on this machine (`external_ready=false`), so external
  confirmation remains open.

## EXP-087: Native CI Supply-Chain Contract

- Command: `make native-ci-contract-test`; `make native-ci-contract-sample`;
  `make native-evaluation-index-test evaluation-index-sample`
- Workload: Production CI, container build, SBOM, scan, and signing contract validation
- Evidence files:
  - `.github/workflows/ci.yml`
  - `native/go/tryops-ci-contract/`
  - `artifacts/eval/ci/native_ci_contract.json`
  - `artifacts/eval/security/vulnerability_scan_report.json`
  - `artifacts/eval/supply_chain/supply_chain_report.json`
  - `artifacts/eval/containers/native_container_contract_report.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the workflow now runs Python, Node, Go, Rust, and C++ contract checks, validates Compose,
  uploads CI evidence artifacts, builds seven container image roles with Docker Buildx metadata,
  generates Syft SPDX SBOMs, gates HIGH/CRITICAL Trivy findings, and signs pushed images with
  Cosign keyless OIDC on non-PR runs. The native Go contract passed 16/16 checks and is surfaced as
  `ci_contract` in the evaluation index.
- Notes: this partially completes PA062. Local `production_ready=false` because `syft`, `trivy`, and
  `cosign` are not installed in this workspace; the GitHub workflow is ready to execute those tools
  in CI.

## EXP-088: Native Secret Rotation And Workload Identity Contract

- Command: `make native-secret-rotation-contract-test`; `make native-secret-rotation-contract-sample`;
  `make native-evaluation-index-test evaluation-index-sample`
- Workload: Vault-backed secret management, Kubernetes workload identity, and API-key rotation
  contract validation for PA060
- Evidence files:
  - `configs/secret_rotation_policy.json`
  - `infra/kubernetes/secret-management/vault-secretstore.yaml`
  - `infra/kubernetes/secret-management/tryops-external-secrets.yaml`
  - `.env.example`
  - `native/go/tryops-secret-rotation-contract/`
  - `artifacts/eval/secrets/native_secret_rotation_contract.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: the split native Go verifier validates Vault KV provider settings, Kubernetes auth role,
  SPIFFE-ready workload identity metadata, 90-day hash-only API-key rotation with 7-day overlap,
  8 managed secrets, Compose secret mounts, live identity env knobs, External Secrets coverage,
  `automountServiceAccountToken: false`, and a projected service-account token with `audience=vault`.
  Latest local plan evidence passes 50/50 checks and is highlighted as `secret_rotation` by the
  evaluation index.
- Notes: this partially completes PA060. `production_ready=false` is intentional until a real
  Vault/External Secrets deployment is available and `VAULT_ADDR` plus
  `TRYOPS_WORKLOAD_IDENTITY_TOKEN_PATH` are exercised with a live secret fetch and rotation drill.

## EXP-089: Native Dependency Lock Contract

- Command: `uv lock`; `make native-dependency-lock-contract-test`;
  `make native-dependency-lock-contract-sample`; `make native-ci-contract-test`;
  `make native-evaluation-index-test evaluation-index-sample`
- Workload: PA063 dependency-lock reproducibility across Python, Node, Rust, and Go surfaces
- Evidence files:
  - `pyproject.toml`
  - `uv.lock`
  - `web/package-lock.json`
  - `native/rust/tryops-gateway/Cargo.lock`
  - `native/go/*/go.mod`
  - `native/go/*/go.sum`
  - `native/go/tryops-dependency-lock-contract/`
  - `artifacts/eval/dependencies/native_dependency_lock_contract.json`
  - `artifacts/eval/evaluation_index/evaluation_index.json`
- Outcome: `uv.lock` pins the Python project resolution, including `accelerate=1.14.0`,
  `bitsandbytes=0.49.2`, `torch=2.11.0`, `transformers=5.11.0`, and `vllm=0.22.1`. The split Go
  verifier checks Python, Console, Rust gateway, and native Go module locks and passed 87/87 checks
  with 326 Python packages, 59 Node packages, 228 Rust crates, and 30 Go modules. The evaluation
  index highlights the report as `dependency_lock`.
- Notes: this closes PA063 for local/native reproducibility evidence. The older generated
  `requirements.lock` remains as a supply-chain fallback artifact, while `uv.lock` is the canonical
  resolved Python project lock.
