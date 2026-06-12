# TryOps

Enterprise open-source MLOps platform for Virtual Try-On and optimized LLM serving.

The project thesis is simple: MLOps is the product. VTON and LLM optimization are the proof workloads used to show reproducibility, governance, model promotion, monitoring, rollback, and continuous improvement.

## What Exists Now

This is the day-one execution scaffold:

- Open-source enterprise architecture and roadmap: `MLOPS_VTON_LLM_ENTERPRISE_ROADMAP.md`
- Runnable Python package under `src/tryops`
- Promotion policy gate with sample passing and failing candidates
- Dataset manifest validator
- VTON and LLM metric summary helpers
- Deterministic local LLM baseline with structured output, safety flags, quality scoring, latency, memory, and cost metrics
- LLM prefill/decode phase timing in benchmark records, structured logs, and Prometheus metrics
- Real diffusion Virtual Try-On: SD1.5 inpainting on CUDA refines a garment composited onto the person (real pixels), behind the unchanged `tryops.vton_baseline.v1` contract with a deterministic fallback (`make vton-real-sample`)
- Real GPU LLM path (R1): `SmolLM2-135M-Instruct` via Transformers on CUDA behind the same `tryops.llm_generation.v1` contract, with a per-record deterministic fallback
- Real LLM quantization Pareto evidence and generated optimization report for fp16-style, bitsandbytes 8-bit, and bitsandbytes 4-bit variants
- Native C++ benchmark statistics + SLO engine (`tryops_perf_stats`): p50/p95/p99 latency, throughput, and pass/fail SLO gating in compiled code rather than Python
- Native C++ multi-window burn-rate engine (`tryops_burn_rate`): LLM/VTON/control-plane error budgets, page/ticket alerts, and Prometheus burn-rate rules
- Native-backed chaos drill and auto rollback: C++ fault evaluator for GPU OOM, slow decode, corrupted weights, and poisoned candidates, feeding the C++ burn-rate engine and rollback records
- Green-MLOps energy/carbon (Theme M): real NVML GPU power sampling + native C++ `tryops_energy_stats` (Wh, CO2e, Software Carbon Intensity, energy-delay product) + a carbon-aware promotion gate, with a deterministic fallback for offline runs
- `/v1` API contract with readiness, structured errors, request IDs, safe aliases, canary routing, and metrics
- Endpoint smoke report for `/v1/ready`, `/v1/llm/generate`, `/v1/vton/infer`, and `/v1/metrics`
- Usage-based quota checks for LLM and VTON requests with hashed user telemetry
- FinOps unit economics, tenant budget showback, budget alerts, semantic-cache hit/savings evidence, and cost/capacity dashboard panels with energy/CO2e plus cost-vs-energy views
- Runtime LLM guardrails: Rust gateway edge enforcement, PII redaction, native Go sidecar/CLI prompt-output classifier, structured-output gate, OWASP LLM 2025 report, and promotion-gate input
- Optimized LLM fallback routing from unavailable optimized aliases to the baseline route
- Timeout handling and async VTON job mode with queue-depth metrics
- Least-privilege API-key simulation for promotion and lineage admin actions
- Structured JSONL API logs and latency/quality alert threshold reports
- Provisioned Grafana service, model-quality, and cost/capacity dashboards
- Local drift reports for VTON image metadata and LLM prompt/topic distributions
- OpenTelemetry-compatible trace/span IDs, `traceparent` propagation, sanitized span JSONL, and trace metrics
- NIST AI RMF, OWASP LLM 2025, and responsible-AI residual-risk mapping evidence
- Dependency lockfile, local SPDX SBOM fallback, and model/dataset license inventories
- Native C++ model artifact scanner enforcing SafeTensors-only promotion and rejecting pickle-family `.bin` weights
- Kubeflow-target orchestration skeleton plus Argo CD / Argo Rollouts GitOps manifests for deployment packaging
- Model lineage record builder plus OpenLineage-standard RunEvent emission
- FastAPI product backend for VTON, LLM, promotion, history, feedback, dashboard, and model-registry endpoints
- Local promotion pipeline that writes model card, data card, internal lineage, OpenLineage, validation, and decision artifacts
- Native production boundary under `native/`: modular Rust gateway artifact/proxy front door with Go-sidecar LLM guardrails at the edge, verified Go controller/guardrail services, and seventeen compiled C++ engines
- Native Go guardrail sidecar integrated into both the Rust gateway edge path and `/v1/llm/generate`, with CLI and Python fallbacks for offline runs
- Native Go signed-PR promotion trigger that verifies GitHub-style HMAC webhook delivery before accepting merged promotion PR evidence
- C++ policy CLI integrated into the Python promotion path as native decision evidence
- C++ model artifact scanner integrated into Python, C++, and Rego promotion gates
- C++ model provenance verifier integrated into local DSSE/SLSA model signing evidence and promotion gates
- C++ OpenLineage validator integrated into promotion and deployment release evidence
- C++ GitOps manifest validator integrated into Argo CD / Argo Rollouts deployment packages
- Native Go registry-webhook deployment trigger that verifies signed MLflow-style alias events before issuing GitOps sync and canary rollout actions
- C++ online experiment router integrated with the routing layer for guarded A/B allocation, holdback, and UCB-style bandit traffic shifts
- C++ online experiment statistics engine for holdback uplift confidence intervals and sequential early-stop decisions
- C++ continuous-batching scheduler benchmark comparing static request-level batching with iteration-level admission
- C++ chaos scenario evaluator integrated into SLO burn-rate and rollback drills
- C++ semantic-cache lookup CLI integrated into `/v1/llm/generate` and `make finops-sample`
- C++ image metrics CLI integrated into VTON comparison artifacts
- C++ VTON preprocessing CLI integrated into optional mask and pose artifacts
- C++ VTON advanced evaluation CLI integrated into identity, masked-fidelity, pose, fairness, and Bradley-Terry evidence
- Modular Rust gateway artifact vs Python FastAPI benchmark (`make gateway-benchmark`), `/api/*` reverse-proxy smoke, and native Prometheus gateway metrics for non-Python serving-boundary evidence
- Garment-preservation similarity proxy with OpenCLIP-ready reporting
- Docker Compose product stack for Rust gateway, FastAPI, MLflow, MinIO, PostgreSQL, Prometheus, Grafana, and Go guardrail
- OPA/Rego policy sketch for model promotion
- Tests that run with the Python standard library

## Chosen Open-Source Stack

- Pipelines: Kubeflow Pipelines
- Registry and tracking: MLflow
- Data and artifact versioning: DVC plus MinIO
- Serving: FastAPI locally, KServe for the enterprise deployment profile
- Production boundary: Rust gateway and Go platform controller
- LLM serving: vLLM
- Semantic cache: native C++ hot path locally, FAISS/Qdrant-ready vector lookup for production
- Monitoring: Prometheus, Grafana, OpenTelemetry, Evidently
- Governance: OPA/Rego, model cards, data cards, risk register
- Supply chain: SafeTensors, native C++ model scanning/provenance verification, Trivy, Syft, Cosign, Sigstore model signing

## Quickstart

Run the standard-library test suite:

```bash
make test
```

Run the native online experimentation sample:

```bash
make experiment-routing-sample
make experiment-analysis-sample
```

Validate a passing sample candidate:

```bash
make validate-sample
```

Validate a failing sample candidate:

```bash
python scripts/validate_candidate.py samples/candidates/vton_candidate_bad.json --stage champion
```

Run the first local promotion pipeline and generate evidence artifacts:

```bash
make pipeline-sample
```

Run the synthetic VTON baseline:

```bash
make vton-baseline-sample
```

Run optional VTON mask and pose preprocessing:

```bash
make vton-preprocess-sample
```

Submit and poll a local async VTON job:

```bash
make vton-job-sample
```

Run garment-preservation similarity:

```bash
make vton-garment-similarity-sample
```

Run advanced VTON evaluation and fairness evidence:

```bash
make vton-advanced-eval-sample
```

Run the local LLM baseline benchmark:

```bash
make llm-benchmark-sample
```

Run the native continuous-batching scheduler benchmark:

```bash
make llm-continuous-batching-sample
```

Run the real GPU LLM benchmark (R1; needs `pip install .[ml]`, a CUDA GPU, and HuggingFace access; falls back to the deterministic baseline per record otherwise):

```bash
make llm-real-sample
```

Compute benchmark percentiles and an SLO verdict with the native C++ engine:

```bash
make native-perf-stats-sample
```

Evaluate SLO error-budget burn rates with the native C++ engine:

```bash
make slo-burn-rate-sample
```

Measure GPU energy/carbon and run the carbon-aware gate (smoke-safe; real NVML when a GPU is present, deterministic fallback otherwise):

```bash
make energy-demo-sample
```

Run the real per-variant GPU energy sweep (Theme M; Wh-per-1k-tokens + Software Carbon Intensity per fp16/8-bit/4-bit variant; needs a CUDA GPU + bitsandbytes):

```bash
make energy-sample
```

Run the real GPU quantization Pareto sweep (R2; fp16 vs 8-bit vs 4-bit, each SLO-gated by the native C++ engine; needs `pip install .[ml]` + bitsandbytes + a CUDA GPU, falls back to the deterministic baseline otherwise):

```bash
make llm-pareto-sample
```

Generate the LLM quality-latency-memory optimization report from an existing Pareto artifact:

```bash
make llm-optimization-report-sample
```

Exercise the signed registry-webhook deployment trigger:

```bash
make registry-webhook-sample
```

Exercise the signed promotion-PR controller trigger:

```bash
make signed-pr-promotion-sample
```

Run LLM prompt/output length sensitivity:

```bash
make llm-sensitivity-sample
```

Simulate usage-based quota accounting through the native Rust gateway:

```bash
make quota-sample
```

Generate FinOps unit economics, budget showback, and native semantic-cache evidence:

```bash
make finops-sample
```

Evaluate least-privilege admin API keys:

```bash
make auth-sample
```

Simulate optimized LLM fallback to baseline:

```bash
make llm-fallback-sample
```

Regenerate the local VTON and LLM benchmark artifacts:

```bash
make benchmark-sample
```

Create deployment release artifacts:

```bash
make deploy-package-sample
```

Run the SRE chaos drill and auto rollback evidence:

```bash
make chaos-sample
```

Compile and run the native C++ policy bridge:

```bash
make native-policy-sample
```

Compile and run the native C++ image metrics bridge:

```bash
make native-image-metrics-sample
```

Compile and run the native C++ VTON preprocessing bridge:

```bash
make native-vton-preprocess-sample
```

Run a local LLM concurrency load test:

```bash
make llm-load-sample
```

Evaluate runtime LLM guardrails and write the OWASP LLM 2025 guardrail report:

```bash
make guardrail-sample
```

Run the native Go guardrail sidecar smoke test:

```bash
make native-guardrail-smoke
```

Evaluate local latency and quality alert thresholds:

```bash
make alert-sample
```

Validate provisioned Grafana dashboards:

```bash
make dashboard-sample
```

Generate local image and prompt drift reports:

```bash
make drift-sample
```

Smoke test the local API endpoint contract:

```bash
make endpoint-smoke-sample
```

Generate governance and responsible-AI risk mapping evidence:

```bash
make governance-sample
```

Generate dependency lock, SBOM, and source/license evidence:

```bash
make supply-chain-sample
```

Run the native C++ SafeTensors-only model artifact gate:

```bash
make model-supply-chain-sample
```

Generate promotion evidence with OpenLineage-standard lineage and native validation:

```bash
make pipeline-sample
```

Generate the Kubeflow-target orchestration skeleton:

```bash
make orchestration-sample
```

Compile and run the native C++ policy engine:

```bash
make native-cpp-test
```

Compile the native C++ OpenLineage validator:

```bash
make native-openlineage-build
```

Check native toolchain availability:

```bash
make native-tooling
```

Start the open-source service stack after installing dependencies and Docker:

```bash
make app-up
```

API contract and observability notes:

- `docs/api_contract.md`
- `docs/observability_contract.md`
- `docs/dashboard_design.md`
- `docs/chaos_reliability.md`
- `docs/drift_monitoring.md`
- `docs/enterprise_quota.md`
- `docs/finops_semantic_cache.md`
- `docs/admin_auth.md`
- `docs/serving_controls.md`
- `docs/release_engineering.md`
- `docs/reproducibility_checklist.md`
- `docs/native_image_metrics.md`
- `docs/vton_preprocessing.md`
- `docs/garment_similarity.md`
- `docs/llm_sensitivity.md`
- `docs/llm_phase_timing.md`
- `docs/opentelemetry_tracing.md`
- `docs/responsible_ai_risk_mapping.md`
- `docs/supply_chain.md`
- `docs/orchestration.md`

## Project Shape

```text
configs/              Project and promotion settings
contracts/            JSON request schemas
docs/                 Architecture, governance, execution notes
infra/                Prometheus, Grafana, and deployment config
policies/             OPA/Rego policy
samples/              Sample candidate payloads
scripts/              Local automation
src/tryops/           Python package
tests/                Standard-library tests
```

## First Execution Milestone

The first milestone is not "train a model." It is:

1. Validate data.
2. Run a benchmark.
3. Produce an evaluation report.
4. Register a candidate.
5. Block or allow promotion through policy.
6. Emit lineage that links model, data, code, run, and artifacts.

That is the foundation for the VTON and LLM work.
