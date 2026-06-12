# TryOps: An Enterprise MLOps Platform for Governed Virtual Try-On and Efficient LLM Serving

**Final Report (working draft)** · Date: 2026-06-11 · Source roadmap: `MLOPS_VTON_LLM_ENTERPRISE_ROADMAP.md` · Authoritative reality audit: `docs/roadmap_audit.md`

---

## 1. Abstract

TryOps is an enterprise ML operating system in which models are treated as governed production assets rather than notebook outputs. Two demanding workloads — diffusion-based Virtual Try-On (VTON) and quantized Large Language Model (LLM) serving — are pushed through a single reproducible spine: versioned data → tracked experiment → evaluated candidate → policy-gated promotion → signed deployment → live monitoring → drift-triggered improvement. The contribution is not a model; it is a platform whose defining claim is that *no model reaches users without evaluation evidence, a passing policy gate, and traceable lineage, and every production output can be replayed from its data, code, config, and run hashes.* The platform is built simulation-first — a deterministic, offline-reproducible spine that runs on any machine — and then has real GPU backends slotted in behind unchanged contracts. On an NVIDIA L4 we executed real small-LLM inference, a real quantization Pareto sweep, a native C++ SLO engine, and real GPU energy/carbon measurement. The results include a counter-intuitive, defense-worthy finding: on this hardware, weight quantization *increases* energy-per-token even as it reduces VRAM, because slower decode keeps the GPU busy longer.

## 2. Introduction and Motivation

Most student ML projects end at "I trained a model and it scores X." Production ML is the opposite problem: the model is the easy 10%, and the operating system around it — reproducibility, governance, promotion gates, monitoring, rollback, cost, security, and continuous improvement — is the hard 90% that determines whether a model can be trusted in production. TryOps makes that operating system the deliverable, and uses VTON (computer vision, GPU-heavy, hard-to-measure quality) and LLM optimization (latency/throughput/memory-bound) as two stress-test workloads that exercise opposite corners of the design space.

## 3. Problem Statement

Production ML is more than model training. A serious platform must answer: How are data and models versioned and reproduced? How is a candidate evaluated and *blocked* if it regresses? How is promotion governed by policy rather than human judgment? How is the system observed, and how does it recover from failure? How are optimization claims measured honestly? TryOps answers each of these with running code and verifiable artifacts.

## 4. Research Questions

1. What architecture makes VTON and optimized-LLM systems reproducible, governable, measurable, and continuously deployable?
2. How much do LLM quantization methods trade off quality, latency, throughput, memory, **and energy**?
3. How can model promotion be controlled with enterprise policy gates instead of manual notebook decisions?
4. How can the production boundary avoid relying on Python?
5. What evidence convinces an evaluator the system is production-minded rather than demo-only?

## 5. Related Work

- **MLOps maturity & lifecycle:** Google's CD/automation pipelines and Azure's MLOps maturity model define automated validation, registry, metadata, and monitoring as production requirements; MLflow provides registry/lineage.
- **VTON:** VITON-HD, HR-VITON (classical warping baselines); StableVITON, IDM-VTON, FLDM-VTON, CatVTON (diffusion-based; CatVTON chosen as the lowest-VRAM target).
- **LLM optimization:** GPTQ, SmoothQuant, AWQ (quantization); FlashAttention, vLLM, TensorRT-LLM (serving).
- **Governance & supply chain:** NIST AI RMF, OWASP LLM Top-10 (2025), SLSA, Sigstore, SBOM tooling (Syft/Trivy/Cosign).
- **Sustainability (Wave 2):** CodeCarbon and the Software Carbon Intensity (SCI) specification for per-inference energy/carbon.
- **Native boundary:** Axum (Rust), Kubebuilder (Go), ONNX Runtime / Triton — informing the decision to carry the production boundary in compiled languages.

The project maintains a living literature table in `docs/literature_review.md`.

## 6. System Architecture

Ten layers: (1) product/UI, (2) API gateway/service boundary, (3) model serving, (4) ML pipelines, (5) registry & metadata, (6) data platform, (7) evaluation, (8) observability, (9) governance & risk, (10) infrastructure. The grading spine is MLOps maturity: every feature must support reproducibility, automation, governance, observability, reliability, or measurable optimization. Architecture detail lives in `docs/architecture.md`; the design decisions and "what breaks first in production" review are in `docs/architecture_review.md`.

A central discipline — **simulation-first** — runs through the whole system: a deterministic spine establishes every contract, gate, metric, and dashboard offline, and real GPU backends are slotted in behind the *same* contracts. Every real component keeps a working degraded-mode fallback, so `make smoke` runs end-to-end on a machine with no GPU, while the same `make` targets exercise real models when a GPU is present.

## 7. Data Governance

Raw → validated → processed → benchmark → feedback → archived data zones; dataset/artifact versioning with DVC + MinIO; data contracts for person/garment images and prompts; privacy rules for user-uploaded images; pipeline-generated data cards. Detail in `docs/data_governance.md`, `docs/data_versioning.md`, and `docs/dataset_inventory.md`. Every run records dataset version, code version, and hardware in its run context.

## 8. VTON Methodology

A deterministic naive VTON baseline produces a generated PNG plus a JSON sidecar and lineage record, exercising the full preprocessing → inference → evaluation → comparison path offline. Optional mask/pose preprocessing runs through a native C++ CLI. Garment preservation is scored with an OpenCLIP-ready proxy, and advanced identity/fairness/preference evidence now runs through `tryops_vton_eval` (`make vton-advanced-eval-sample`). A **real** latent-diffusion try-on is now executed on the L4: the garment is composited onto the torso (preserving its pixels) and Stable-Diffusion 1.5 inpainting refines that region photorealistically, behind the unchanged `tryops.vton_baseline.v1` contract with a deterministic fallback (`make vton-real-sample`; 3.3 s, 2.8 GB VRAM; native C++ metrics PSNR 16.8 / SSIM 0.54 vs the person). Dedicated warping models (CatVTON primary, IDM-VTON stretch), neural preprocessing (SAM/SCHP/DensePose/OpenPose), and representative human fairness panels remain the higher-fidelity stretch. Detail: `docs/vton_baseline.md`, `docs/vton_preprocessing.md`, `docs/vton_evaluation.md`, `docs/garment_similarity.md`.

## 9. LLM Optimization Methodology

The LLM workload is a project assistant/evaluator. The deterministic baseline (`tryops.llm_generation.v1`) gives structured output, safety flags, quality scoring, latency, memory, and cost — runnable before any weights download. The **real** path (R1) loads `SmolLM2-135M-Instruct` via Transformers on CUDA behind the *unchanged* contract, with a per-record deterministic fallback. The **optimization** path (R2) sweeps a quantization matrix (fp16 / bitsandbytes 8-bit / bitsandbytes 4-bit NF4) over one base model, holding the eval set and hardware fixed, and computes a non-dominated Pareto frontier with an auto-recommendation. Each variant's latency/throughput is gated by the native C++ SLO engine, and (Theme M) its real GPU energy is measured. Continuous-batching scheduler evidence now runs in native C++: 20 mixed requests show 1.218x modeled throughput, 19.1% lower p95 latency, and decode-slot utilization 0.623 -> 1.0 vs static batching. Detail: `docs/llm_baseline.md`, `docs/llm_results.md`, `docs/llm_sensitivity.md`, `docs/llm_continuous_batching.md`, `docs/green_mlops.md`.

## 10. MLOps Pipeline Design

Pipelines for data validation, VTON preprocessing/baseline/comparison, LLM benchmark/sensitivity/Pareto, model registration, promotion, and deployment packaging. A Kubeflow-target orchestration skeleton defines a validated seven-step enterprise DAG. Every pipeline run carries a run ID, git/code version, dataset version, and hardware in its run context; one-command reproduction is provided via `make` targets. Reproducibility checklist: `docs/reproducibility_checklist.md`.

## 11. Registry, Policy Gates, and Model Governance

A local JSON registry records candidate/challenger/champion/archived/rejected with lineage, owners, cards, and approval status. Promotion is governed by policy-as-code: the OPA/Rego sketch and a **compiled C++ policy engine** (`tryops_policy`) jointly decide whether a candidate may move stage, requiring tests, metrics, model card, data card, and supply-chain evidence. A signed GitHub-style promotion PR can be verified by the Go controller before alias sync (`make signed-pr-promotion-sample`), and a signed MLflow-style registry alias webhook can then be translated into GitOps sync plus canary rollout actions (`make registry-webhook-sample`). A failing candidate is provably blocked (`make validate-bad`). Detail: `docs/model_governance.md`, generated artifacts under `reports/generated/`.

## 12. Native Production Boundary (Rust, Go, C++)

A core thesis decision: **Python is the ML lab layer; the production boundary is carried by compiled languages.** The repository contains a Rust Axum gateway that builds, tests, smokes, owns quota admission locally, fronts the product stack by proxying `/api/*` to the backend `/v1/*` contract with request IDs plus edge limits, and exports native Prometheus metrics; a Go reconciliation controller and Go guardrail sidecar that build and smoke locally; and **seventeen compiled, tested C++ engines** that sit on hot paths.

| C++ engine | Role | Make target |
|---|---|---|
| `tryops_policy` | promotion-gate decision evidence | `native-policy-sample`, `native-cpp-test` |
| `tryops_image_metrics` | VTON MSE/PSNR/dHash comparison | `native-image-metrics-sample` |
| `tryops_vton_preprocess` | mask/pose preprocessing | `native-vton-preprocess-sample` |
| `tryops_vton_eval` | identity, masked fidelity, pose, fairness, and Bradley-Terry ranking | `vton-advanced-eval-sample` |
| `tryops_perf_stats` | latency-percentile + throughput + SLO verdict | `native-perf-stats-sample` |
| `tryops_burn_rate` | multi-window SLO burn-rate alerting | `slo-burn-rate-sample`, `chaos-sample` |
| `tryops_energy_stats` | energy/CO2e/SCI/EDP + carbon-aware verdict | `energy-demo-sample` |
| `tryops_eval_stats` | bootstrap confidence intervals and leaderboard statistics | `eval-leaderboard-sample` |
| `tryops_experiment_router` | guarded A/B, holdback, and UCB-style bandit routing | `experiment-routing-sample` |
| `tryops_experiment_stats` | holdback uplift CIs and sequential early-stop decisions | `experiment-analysis-sample` |
| `tryops_batch_scheduler` | static-vs-continuous LLM batching scheduler evidence | `llm-continuous-batching-sample` |
| `tryops_model_scan` | SafeTensors-only model artifact scanning | `model-supply-chain-sample` |
| `tryops_model_provenance` | model signature/provenance verification | `model-supply-chain-sample` |
| `tryops_openlineage` | OpenLineage RunEvent validation | `pipeline-sample` |
| `tryops_gitops` | Argo CD / Argo Rollouts manifest validation | `deploy-package-sample` |
| `tryops_semantic_cache` | low-latency semantic-cache lookup | `finops-sample` |
| `tryops_chaos` | SRE fault classification for rollback drills | `chaos-sample` |

Each follows one protocol (stdin `key=value` → stdout JSON, error JSON + non-zero exit) with a Python marshaling bridge that degrades gracefully when the binary is absent. This moves the performance- and policy-critical work off Python without sacrificing offline reproducibility.

## 13. Observability and Feedback Loops

Prometheus-style metrics (latency, error rate, model version, tokens/sec, queue depth, prefill/decode phase timing), structured JSONL logs with sanitized metadata, provisioned Grafana dashboards (service, model-quality, cost/capacity), alert-threshold reports with Prometheus alert rules, and local drift reports for image-metadata and prompt-length/topic distributions. Detail: `docs/observability_contract.md`, `docs/dashboard_design.md`, `docs/drift_monitoring.md`.

## 14. Security and Responsible AI

- **NIST AI RMF** risk mapping and **OWASP LLM Top-10 (2025)** control mapping are generated as governance evidence (`artifacts/eval/governance/governance_report.json`; `docs/responsible_ai_risk_mapping.md`).
- LLM security tests cover prompt injection, sensitive-information disclosure, and oversized-payload DoS; image-payload abuse tests cover malformed/oversized files.
- Supply chain: dependency lockfile, local SPDX SBOM fallback, model-source pins, dataset license inventory, SafeTensors-only model scanning, local in-toto/SLSA provenance, and native C++ provenance verification (`docs/supply_chain.md`, `docs/model_supply_chain.md`).
- Wave 2 extends this to real Sigstore keyless OIDC/Rekor verification, runtime guardrails, and a carbon-aware gate.
- **Residual risks & production-readiness boundaries** are stated honestly in the Reality Ledger and `docs/known_limitations.md`.

## 15. Evaluation Protocol

All measurements are reproducible from a clean checkout. Hardware: NVIDIA L4 (23 GB), CUDA, torch 2.11. LLM evaluation uses a fixed golden prompt set; metrics are latency (p50/p95/p99 via the native engine), decode throughput, peak `torch.cuda` VRAM, a rubric quality proxy, real GPU energy (NVML, integrated over wall-time), and a native SLO/carbon verdict. The deterministic spine is validated by 219 unit/integration tests and `make smoke` (exit 0). GPU tranches (`llm-real-sample`, `llm-pareto-sample`, `energy-sample`) are excluded from `smoke` and degrade to the deterministic baseline when no GPU is present.

## 16. Results

### 16.1 Real LLM inference (R1)
`SmolLM2-135M-Instruct` on CUDA (fp16): ~**18.5 tok/s**, **0.28 GB** peak VRAM on the golden set, emitting the unchanged `tryops.llm_benchmark.v1` artifact.

### 16.2 Quantization Pareto (R2) — Qwen2.5-0.5B-Instruct on the L4

| Variant | VRAM | tok/s | quality | native SLO |
|---|---|---|---|---|
| fp16 | 1.01 GB | 21.8 | 0.25 | pass |
| 8-bit | 0.65 GB | 4.5 | 0.25 | **fail (dominated)** |
| 4-bit (NF4) | **0.48 GB** | 11.3 | 0.28 | pass → **recommended** |

The native engine identified 8-bit as a *dominated* variant (slower **and** larger than 4-bit on this small model) and recommended 4-bit: **2.1× VRAM reduction**, SLO-passing.

### 16.3 Adapter-specific SLO calibration (native `tryops_perf_stats`)
The real GPU model (p95 ≈ 7.6 s) **fails** an SLO of 100 ms p95 that was calibrated to the sub-millisecond deterministic baseline, and **passes** a GPU-calibrated SLO — demonstrating, in compiled code, that SLOs are adapter-specific and must be re-baselined per backend.

### 16.4 Energy & carbon (Theme M) — measured on the L4 (grid 475 gCO2e/kWh)

| Variant | Wh / 1k tokens | gCO2e / 1k tokens | vs fp16 |
|---|---|---|---|
| **fp16** | **0.52** | 0.25 | greenest |
| 8-bit | 1.78 | 0.85 | **3.4× more energy** |
| 4-bit | 0.81 | 0.39 | 1.55× more energy |

**Headline finding:** quantization's VRAM win comes at an energy cost on this hardware — bitsandbytes' slower per-token decode keeps the GPU busy longer, so joules-per-token rise even as VRAM falls. This is precisely the tradeoff the carbon-aware promotion gate exists to surface.

### 16.5 Native vs Python serving throughput (measured)
The native production boundary is not a claim but a measured result. On the identical `/health` handler, head-to-head under 50 keep-alive connections:

| Scenario | Native path | Native req/s | Python path | Python req/s |
|---|---|---:|---|---:|
| `GET /health` | Rust gateway | **24,841** | FastAPI direct | 1,539 |
| Direct validated promotion POST | Rust preflight | **22,261** | FastAPI policy/auth | 755 |
| Full edge promotion POST | Rust gateway -> FastAPI | 699 | FastAPI direct | **759** |

The native Go load driver removes the earlier Python/GIL benchmark-driver limitation: direct Rust serving is **16.14x** faster on `/health` and **29.49x** faster on the direct validated promotion POST. The full edge proxy path is measured separately and honestly shows the cost of adding signed-artifact preflight plus proxying in front of the same FastAPI policy route. The modular Rust gateway artifact reverse-proxies `/api/*`, injects request IDs, propagates `traceparent`, enforces signed-artifact preflight, rate limits, payload limits, Go-sidecar LLM edge guardrails, and native quota pre-admission through `/v1/quota/check` plus the `quota-check` batch CLI. The modular Go controller reconciles promotion decisions with HTTP 202/422 evidence. Commands: `make gateway-benchmark-native`, `make gateway-benchmark`, `make native-rust-smoke`, `make native-edge-guardrail-smoke`, `make native-go-smoke`, `make quota-sample`.

### 16.6 Platform maturity
253 backlog items done / 14 partial / 35 not-started (83.8%); 221 Python tests plus 16 Rust gateway unit tests; `make smoke` green; seventeen compiled C++ engines, including a modular semantic-cache core/CLI/test split; native Go benchmark load driver; full lineage/OpenLineage/GitOps/signed-PR/webhook/experimentation/quota/VTON-fairness/batch-scheduling/energy-dashboard/rust-edge/rust-metrics/rust-edge-guardrail/product-backend/promotion/rollback/chaos artifacts.

## 17. Failure Analysis

- **Rubric overfit (real, important):** the golden rubric was tuned to the deterministic baseline's exact phrasing, so real models score only ~0.25 quality despite producing fluent answers. This is a genuine evaluation bug, not a model regression, and motivates Wave 2 Theme N (model-agnostic semantic scoring + an LLM-as-judge with statistical confidence intervals).
- **8-bit quantization regressed on every axis** (slower, larger than 4-bit, more energy) on a small model — a reminder that quantization wins are model- and hardware-dependent and must be measured, not assumed.
- **SLO thresholds do not transfer between adapters** — a baseline-calibrated gate falsely fails a real model; thresholds must be re-baselined per backend.

## 18. Limitations

Real diffusion VTON, live vLLM serving, AWQ/GPTQ/GGUF, live MLflow/DVC/MinIO writes, real Sigstore keyless OIDC/Rekor model signing, representative VTON fairness panels, and KServe/Kubeflow deployment are designed and scoped but not yet executed in this workspace. Native C++ continuous-batching scheduler evidence exists, but it is not a live vLLM server benchmark. Go, Rust, and C++ native paths are locally verified. The quantization energy finding is specific to a 0.5B model on an L4; larger models and AWQ may shift the result. The carbon figure depends on one documented assumption (grid intensity). The honest, file-by-file boundary between real and simulated is maintained in `docs/roadmap_audit.md` and the roadmap's Reality Ledger.

## 19. Future Work

Wave 2 (designed, in the roadmap, themes M–U): **M Green MLOps** (done), **N rigorous evaluation + LLM-as-judge**, **O runtime guardrails (OWASP-2025 enforced)**, **P trustworthy model supply chain (SafeTensors-only, model scanning, Sigstore signing, SLSA provenance)**, **Q FinOps + semantic caching**, **R SRE error budgets + chaos**, **S GitOps CD + OpenLineage**, **T online experimentation** (A/B, guarded bandit, sequential testing, and holdback uplift CIs done), **U VTON fairness + Bradley-Terry preference**. Scaling to real enterprise deployment means rebuilding the Rust gateway in CI, deploying the verified Go controller against a cluster, standing up KServe/Kubeflow, and wiring live exporters for the quality/cost/energy dashboards.

## 20. Conclusion

TryOps demonstrates engineering maturity rather than model novelty. It establishes a reproducible, governed spine, then proves it with real GPU workloads behind unchanged contracts: real LLM inference, a measured quantization Pareto frontier, a compiled SLO engine, and real energy/carbon accounting that overturns a common assumption about quantization. The platform blocks bad models, traces every output to its origins, carries its hot paths in compiled code, and audits its own claims — which is the difference between a demo and a production ML operating system.

---

### Appendix A — Reproduce the headline evidence

```bash
make smoke                 # full deterministic spine: 221 Python tests + every pipeline + native engines
make llm-real-sample       # R1: real SmolLM2-135M on CUDA
make llm-pareto-sample     # R2: real fp16/8-bit/4-bit quantization Pareto, native SLO-gated
make energy-sample         # Theme M: real per-variant GPU energy + Software Carbon Intensity
make native-perf-stats-sample   # native C++ latency/SLO engine
make llm-continuous-batching-sample # native C++ static-vs-continuous scheduler benchmark
make experiment-routing-sample  # native C++ guarded A/B + bandit routing
make experiment-analysis-sample # native C++ holdback uplift + sequential testing
make vton-advanced-eval-sample # native C++ identity/fidelity/pose/fairness/preference ranking
make quota-sample          # native Rust quota admission artifact
make native-rust-smoke     # Rust gateway health + quota accept/reject smoke
make chaos-sample          # native chaos drill + burn-rate-triggered auto rollback
make gateway-benchmark-native # Go load driver: Rust gateway vs FastAPI GET + validated POST paths
make gateway-benchmark     # historical Python-driver lower-bound benchmark
make native-go-smoke       # Go controller build + promotion reconcile smoke
make signed-pr-promotion-sample # signed promotion PR -> alias sync actions
make registry-webhook-sample # signed registry alias event -> GitOps/canary actions
make roadmap-status        # completion snapshot
```

### Appendix B — Key evidence artifacts

`artifacts/eval/llm_real/benchmark.json` · `artifacts/eval/llm_pareto/pareto.json` · `artifacts/eval/perf_stats/perf_stats.json` · `artifacts/eval/energy/energy_sweep.json` · `artifacts/eval/gateway_benchmark/gateway_benchmark.json` · `artifacts/eval/model_supply_chain/model_provenance.json` · `artifacts/eval/signed_pr/signed_pr_promotion_report.json` · `artifacts/eval/registry_webhook/registry_webhook_report.json` · `artifacts/eval/chaos/chaos_drill_report.json` · `artifacts/eval/governance/governance_report.json` · `reports/generated/vton-catvton-2026-06-11-001/` · `docs/roadmap_audit.md`.
