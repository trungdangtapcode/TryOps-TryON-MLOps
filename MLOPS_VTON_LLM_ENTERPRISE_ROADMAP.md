# Enterprise MLOps Roadmap for VTON and LLM Optimization

Date: 2026-06-10 (rev. 2026-06-11: sharpened thesis, honest status legend + reality ledger, GPU real-model tranche, CI/CD supply-chain trust pipeline, control-room UI).

Core theme: MLOps is the project. Virtual try-on and LLM optimization are the proof workloads used to demonstrate a serious, enterprise-grade ML platform.

## Platform Thesis (One Paragraph)

TryOps is an enterprise ML operating system in which models are governed production assets, not notebook outputs. Two demanding workloads — diffusion-based Virtual Try-On (computer vision, heavy GPU, hard-to-measure quality) and quantized LLM serving (language, latency/throughput/memory-bound) — are pushed through one reproducible spine: versioned data to tracked experiment to evaluated candidate to policy-gated promotion to signed deployment to live monitoring to drift-triggered improvement. The grading claim is not "I trained a model." It is: "No model reaches users without evaluation evidence, a passing policy gate, a signed artifact, and traceable lineage; every production output can be replayed from its data, code, config, and run hashes." The deterministic, offline-reproducible simulation spine is the credibility backbone — it makes every gate, metric, and dashboard demoable on any machine — and the GPU-backed real-model tranche (below) replaces stand-ins with real diffusion VTON and real quantized LLMs behind the **same contracts**, so the platform is proven before the models are even loaded.

## Status Legend

Every backlog item and claim in this document uses one of three honest states. This legend exists specifically so an evaluator can trust the checkboxes:

- `[x]` **Done & real** — code runs, produces a verifiable artifact, and is covered by a test or `make smoke`/CI.
- `[~]` **Contract-only / simulated** — the interface, schema, and a deterministic stand-in exist and are tested, but the real backend (GPU model, live server, cloud service) is not yet wired. This is a feature of the simulation-first strategy, not a gap to hide.
- `[ ]` **Not started.**

The authoritative, file-by-file reality audit lives in `docs/roadmap_audit.md` and is the single source of truth when a checkbox and the code disagree.

## Headline Metrics (Target Evidence)

The defense should open on this scoreboard. Every number is an *evidence target* to be filled from reproducible runs, not a marketing claim.

| Dimension | Metric | Target evidence | Source |
| --- | --- | --- | --- |
| LLM optimization | INT4 vs FP16 memory | measured 2.1x (bnb-4bit, Qwen2.5-0.5B); target 3.5x with AWQ/larger model | `make llm-pareto-sample` (real) |
| LLM optimization | INT4/vLLM vs HF FP16 throughput | at least 2x tokens/sec single, 4x at concurrency 16 | vLLM continuous batching bench |
| LLM optimization | Quality retention after quant | at most 2% drop on golden set (judge + rubric) | Pareto report |
| VTON quality | CatVTON on 50-pair benchmark | FID / LPIPS / SSIM / CLIP-garment reported with CIs | `make vton-eval` (real) |
| VTON cost/latency | p50 / p95 + GPU-sec per 100 gens | reported with hardware cost model | cost dashboard |
| MLOps / DORA | Promotion lead time, rollback time | rollback under 60s; lead time tracked | release engineering artifacts |
| Governance | Unsigned/unscanned artifacts promoted | exactly 0 (OPA-enforced) | promotion audit log |
| Reproducibility | Golden-path replay pass rate | 100% from clean checkout | `make smoke` + CI |

## Reality Ledger: Real vs Simulated

This is the honesty centerpiece and itself a maturity signal — a platform that audits its own claims. The deterministic spine below is **real, tested, and reproducible today**; the right column is the GPU-backed tranche that swaps in real backends behind unchanged contracts.

| Capability | Today (`[x]` real spine) | Closing the gap (`[~]` to real) |
| --- | --- | --- |
| LLM inference | **DONE (R1):** real SmolLM2-135M on CUDA via Transformers, unchanged contract, deterministic fallback (`make llm-real-sample`) | Larger Qwen2.5 point + quantized variants |
| Perf SLO gating | **DONE:** native C++ `tryops_perf_stats` computes p50/p95/p99 + throughput + SLO verdict (`make native-perf-stats-sample`) | Feed every quantized variant through it |
| Green MLOps / energy | **DONE (Theme M):** real NVML GPU energy per inference + native C++ `tryops_energy_stats` (kWh, SCI, EDP) + carbon-aware gate (`make energy-sample`). Measured on the L4: fp16 0.52 Wh/1k tokens is **greenest**; 8-bit costs 3.4x and 4-bit 1.55x more energy — quantization's VRAM win comes at an energy cost | Energy Grafana panel; VTON energy; live exporter |
| LLM optimization | **DONE (R2/E010) + E008/E009/E011 harnesses:** real fp16/8-bit/4-bit Pareto sweep of Qwen2.5-0.5B on CUDA, each variant SLO-gated by native C++ (`make llm-pareto-sample`), plus native C++ GGUF preflight over a real SmolLM2 Q2_K artifact (`make llm-gguf-preflight-sample`), native Go GPTQ/AWQ repo/runtime preflight (`make llm-quantized-preflight-sample`), and native Go vLLM OpenAI-compatible serving probe (`make llm-vllm-probe-sample`). Measured: 4-bit NF4 = 2.1x VRAM cut (1.01->0.48 GB), SLO-pass; 8-bit dominated (slower+larger), SLO-fail; GGUF artifact = 88.2 MB, 272 tensors, `mostly_q2_k`; GPTQ/AWQ candidates verified but loader packages missing; local vLLM probe = skipped because `vllm` is not installed | Install GPTQ/AWQ loader runtimes for live loading, add larger model for the 3.5x headline; install llama.cpp CLI for live GGUF generation; install/start vLLM for live serving throughput |
| VTON inference | **DONE (real): real latent-diffusion** try-on on CUDA — garment composited onto the torso then SD1.5 inpainting refines it (real pixels, not just a prompt), behind the unchanged `tryops.vton_baseline.v1` contract with a deterministic fallback (`make vton-real-sample`). Measured on the L4: 3.3 s, 2.8 GB VRAM; native C++ metrics PSNR 16.8 / SSIM 0.54 | CatVTON/IDM-VTON dedicated warping; SAM/DensePose masks |
| VTON preprocessing | Heuristic C++ mask/pose CLI | SAM / SCHP / DensePose / OpenPose adapters |
| Garment similarity | **DONE:** deterministic garment-patch proxy plus verified Transformers CLIP image-image/text scoring on CPU (`make vton-clip-similarity-sample`) | Fixed-set CLIP confidence intervals + OpenCLIP/local checkpoint pinning |
| Registry/tracking | Local JSON registry entries + lineage | Live MLflow server writes + Model Registry aliases |
| Data versioning | **DONE:** DVC repro/push against MinIO plus native Go S3 verifier (`make dvc-minio-sample`) | Clean-machine `dvc pull` restore drill |
| Production boundary | **DONE:** Native boundary is no longer Python-only: Go controller/guardrail sidecar build and smoke (`make native-go-smoke`, `make native-guardrail-smoke`), the Rust Axum gateway builds/smokes, proxies `/api/*`, enforces signed-artifact, quota preflight, and Go-sidecar LLM guardrails at the edge, and seventeen C++ engines cover policy, image metrics, VTON preprocessing/evaluation, perf/SLO, burn-rate, energy, eval stats, online experiment routing/statistics, batch scheduling, model scan, model provenance, OpenLineage validation, GitOps manifest validation, semantic cache, and chaos (`make smoke`). | KServe deploy profile; full-stack production acceptance |
| Eval statistics | **DONE (N):** bootstrap-CI hot path in native C++ `tryops_eval_stats`, used by the leaderboard with a Python fallback | judge-vs-rubric κ at scale with a live Claude judge |
| Serving throughput | **DONE (measured with native driver):** Go stdlib load generator removes the Python/GIL driver limit. Rust gateway vs FastAPI: `/health` **24,841 vs 1,539 req/s (16.14x)**; direct validated promotion POST **22,261 vs 755 req/s (29.49x)**; full edge proxy POST **699 vs 759 req/s (0.92x)**, explicitly measuring the gateway preflight/proxy hop (`make gateway-benchmark-native`). Legacy Python-driven benchmark remains as historical lower-bound evidence (`make gateway-benchmark`). | external wrk/k6 confirmation; full KServe/vLLM validated path |
| Supply chain | **DONE:** policy, fallback SBOM, GitHub Actions image SBOM/signing gates, and local live Syft/Trivy/Cosign execution are verified (`make native-ci-contract-live`) | Keyless model transparency/Rekor proof for released model artifacts |
| Monitoring | Local Prometheus rules + Grafana JSON + offline drift | Live exporters + Alertmanager + sanitized live-traffic drift windows |

## Executive Intent

Build an end-to-end MLOps platform that can train, optimize, deploy, evaluate, monitor, govern, and continuously improve two high-impact AI workloads:

1. Virtual Try-On (VTON): image-based garment transfer with measurable visual quality, garment fidelity, identity preservation, latency, cost, and safety controls.
2. LLM Optimization: quantization and inference acceleration for a domain assistant, evaluator, or product reasoning component, with measurable quality, latency, throughput, memory, and cost improvements.

The professor-facing story should not be "I trained a model." The story should be:

"I built an enterprise ML operating system where models are treated as governed production assets. VTON and LLM services move through reproducible pipelines, model registry gates, deployment promotion, monitoring, drift detection, rollback, cost tracking, responsible AI checks, and continuous improvement loops."

## North-Star Demo

The final demo should show one coherent flow:

1. A data change or new experiment triggers an ML pipeline.
2. The pipeline validates data, trains or optimizes a model, evaluates it, registers artifacts, creates a model card, and checks governance gates.
3. A deployment pipeline promotes a candidate model to staging.
4. Automated tests compare baseline and candidate models on quality, latency, cost, safety, and robustness.
5. A controlled release deploys the model.
6. Live dashboards show service health, model quality, inference latency, GPU or CPU memory, cost per request, data drift, feedback trends, and rollback state.
7. A professor can upload a person image and garment image for VTON, then inspect the lineage and production metrics behind the output.
8. A professor can ask the LLM assistant a project question and see optimized variants compared by quantization method, latency, memory, and answer quality.

## Research Basis

Use these sources as the initial evidence base. The project should keep a living literature table with paper summaries, assumptions, limitations, and implementation relevance.

### MLOps and Enterprise Operations

- Google Cloud, "MLOps: Continuous delivery and automation pipelines in machine learning": emphasizes CI/CD/CT, automated data/model validation, metadata, model registry, feature store, and monitoring as production ML requirements. URL: https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning
- Microsoft Azure Architecture Center, "MLOps Maturity Model": defines higher maturity as automated release, tracked experiments, versioned training code and models, production metrics, and retraining triggers. URL: https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-maturity-model
- MLflow Model Registry: centralized model lifecycle management with lineage, versioning, aliases, tags, and governance metadata. URL: https://mlflow.org/docs/latest/ml/model-registry/
- NIST AI Risk Management Framework: risk management for trustworthy AI design, development, use, and evaluation. URL: https://www.nist.gov/itl/ai-risk-management-framework
- OWASP Top 10 for LLM Applications: security risks including prompt injection, insecure outputs, data poisoning, denial of service, supply chain vulnerabilities, sensitive information disclosure, excessive agency, overreliance, and model theft. URL: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- SLSA: supply-chain integrity framework for provenance, tamper resistance, and trusted artifacts. URL: https://slsa.dev/spec/v1.1/about
- OpenTelemetry: observability standard for traces, metrics, logs, context propagation, and instrumentation. URL: https://opentelemetry.io/docs/what-is-opentelemetry/
- Axum: Rust HTTP routing and request-handling library built around Tokio, Hyper, Tower, extractors, predictable errors, and middleware. URL: https://docs.rs/axum/latest/axum/
- Kubebuilder: Go/Kubernetes API and controller framework for declarative APIs, validation, auth, reconciliation, and self-healing behavior. URL: https://book.kubebuilder.io/
- Triton Inference Server: open inference server supporting HTTP/gRPC, batching, model repositories, metrics, tracing, and multiple backends including vLLM, TensorRT, ONNX Runtime, PyTorch, and custom backends. URL: https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/index.html
- ONNX Runtime: cross-platform model accelerator with C/C++/Rust-facing deployment options, hardware execution providers, graph optimization, and model validation requirements. URL: https://onnxruntime.ai/docs/

### Open-Source Stack Sources

- Kubeflow Pipelines: portable, scalable ML workflows using containers on Kubernetes; supports components, artifacts, runs, experiments, and pipeline visualization. URL: https://www.kubeflow.org/docs/components/pipelines/overview/
- KServe: CNCF incubating Kubernetes inference platform for generative and predictive AI, with vLLM support, autoscaling, canary rollouts, routing, explainability, and monitoring hooks. URL: https://github.com/kserve/kserve
- DVC: Git-oriented data, model, pipeline, and experiment versioning for ML projects. URL: https://doc.dvc.org
- Evidently: open-source evaluation, testing, and monitoring for data and AI systems, including LLM evaluation and ML monitoring. URL: https://docs.evidentlyai.com/
- Prometheus: open-source monitoring and alerting with time-series metrics and service-oriented observability. URL: https://prometheus.io/docs/introduction/overview/
- Grafana OSS: open-source dashboards for metrics, logs, traces, alerts, and operational visualization. URL: https://grafana.com/docs/grafana/latest/introduction/
- Open Policy Agent: open-source policy-as-code engine for decisions across APIs, Kubernetes, CI/CD, and infrastructure. URL: https://www.openpolicyagent.org/docs
- Trivy: open-source scanner for vulnerabilities, misconfigurations, secrets, SBOMs, containers, Kubernetes, repositories, and filesystems. URL: https://github.com/aquasecurity/trivy
- Syft: open-source SBOM generator for container images and filesystems. URL: https://github.com/anchore/syft
- Cosign: open-source artifact signing and verification for OCI containers and other artifacts. URL: https://github.com/sigstore/cosign
- Keycloak: CNCF incubating open-source identity and access management for securing applications and services. URL: https://www.keycloak.org/documentation

### VTON Research

- VITON-HD: high-resolution virtual try-on via misalignment-aware normalization. URL: https://arxiv.org/abs/2103.16874
- Dress Code: high-resolution multi-category virtual try-on dataset and benchmark. URL: https://arxiv.org/abs/2204.08532
- HR-VITON: high-resolution virtual try-on with misalignment and occlusion-handled conditions. URL: https://arxiv.org/abs/2206.14180
- StableVITON: semantic correspondence with latent diffusion for virtual try-on. URL: https://arxiv.org/abs/2312.01725
- IDM-VTON: improved diffusion models for authentic virtual try-on in the wild. URL: https://arxiv.org/abs/2403.05139
- FLDM-VTON: faithful latent diffusion model for preserving garment details. URL: https://arxiv.org/abs/2404.14162
- CatVTON: simpler efficient diffusion VTON through concatenation, reduced preprocessing, and lower memory. URL: https://arxiv.org/abs/2407.15886

### LLM Quantization and Acceleration Research

- GPTQ: one-shot post-training quantization for large generative transformers. URL: https://arxiv.org/abs/2210.17323
- SmoothQuant: W8A8 post-training quantization by smoothing activation outliers. URL: https://arxiv.org/abs/2211.10438
- AWQ: activation-aware 4-bit weight quantization for LLM compression and acceleration. URL: https://arxiv.org/abs/2306.00978
- FlashAttention: IO-aware exact attention for memory-efficient transformer training and inference. URL: https://arxiv.org/abs/2205.14135
- vLLM: production-oriented LLM serving with PagedAttention, continuous batching, prefix caching, quantization, optimized kernels, and speculative decoding. URL: https://docs.vllm.ai/en/latest/
- NVIDIA TensorRT-LLM: optimized LLM inference engine creation and runtimes for NVIDIA GPUs. URL: https://docs.nvidia.com/tensorrt-llm/index.html
- Hugging Face Transformers Quantization Overview: practical quantization choices across bits, hardware, calibration, serialization, and fine-tuning. URL: https://huggingface.co/docs/transformers/main/en/quantization/overview

## Golden Path Demo (Exact Commands)

The single rehearsed flow a professor sees. It runs offline on the deterministic spine today, and the same commands exercise real backends once the GPU tranche lands. Each step prints the artifact path it produced so the demo doubles as an evidence tour.

```bash
make smoke                      # 1. full deterministic spine: tests + every pipeline + native bridges
make pipeline-sample            # 2. data -> eval -> registry -> model card -> lineage -> OPA gate
python scripts/validate_candidate.py samples/candidates/vton_candidate_bad.json --stage champion
                                # 3. governance gate BLOCKS a bad model (the money shot)
make vton-compare-sample        # 4. VTON baseline + comparison + failure-gallery artifact
make vton-advanced-eval-sample  # 5. native identity/fidelity/pose/fairness/preference evidence
make llm-benchmark-sample       # 6. LLM golden-prompt benchmark (real Pareto once GPU tranche lands)
make llm-continuous-batching-sample # 7. native C++ static-vs-continuous scheduler evidence
make deploy-package-sample      # 8. signed deployment package + release notes + rollback plan
make rollback-sample            # 9. one-command rollback under target SLO
make drift-sample               # 10. drift reports trigger a re-evaluation candidate
make governance-sample          # 11. NIST AI RMF + OWASP LLM mapping -> implemented controls
make guardrail-sample           # 12. native Go LLM guardrails -> OWASP report + promotion gate input
```

The narrative spine: *a model tries to ship, the platform evaluates it, the policy gate stops the bad one, the good one is signed and deployed with full lineage, monitoring catches drift, and rollback is one command.* Steps 3 and 7 are the two moments that distinguish a platform from a demo.

## Proposed Project Name

TryOps: Enterprise MLOps Platform for Virtual Try-On and Efficient LLM Serving.

## Research Questions

1. What architecture is needed to make VTON and optimized LLM systems reproducible, governable, measurable, and continuously deployable?
2. How much do VTON model choices trade off garment fidelity, identity preservation, perceptual quality, inference latency, and GPU memory?
3. Which LLM optimization methods give the best quality-latency-memory-cost frontier under student hardware constraints?
4. How can ML model promotion be controlled with enterprise-style policy gates instead of manual notebook decisions?
5. How can monitoring detect data drift, model decay, safety issues, and cost regressions across both computer vision and language workloads?
6. What evidence would convince an evaluator that the system is production-minded rather than a demo-only ML experiment?

## Enterprise Architecture

### Layer 1: Product and User Layer

- VTON web UI for person image, garment image, output comparison, and quality metadata.
- LLM assistant UI for project Q&A, experiment explanations, and optimization comparison.
- Admin dashboard for model registry, deployments, incidents, rollbacks, costs, and governance approvals.
- Professor demo mode with seeded examples, reproducible outputs, and architecture walkthrough.

### Layer 2: API Gateway and Service Boundary

- REST or gRPC APIs for VTON inference, LLM inference, model metadata, evaluations, and feedback.
- Auth middleware, request IDs, native Rust quota pre-admission, rate limits, file validation, payload size limits, and audit logging.
- Async job mode for expensive VTON inference and batch evaluations.

### Layer 3: Model Serving

- VTON serving service using a FastAPI container first, then KServe InferenceService for the enterprise deployment profile.
- LLM serving using vLLM for open-source models, exposed through the API gateway in local mode and through KServe in the enterprise deployment profile.
- Model routing layer that can compare baseline, candidate, quantized, and experimental variants.
- Canary and shadow deployment support for evaluation without full user exposure.

### Layer 4: ML Pipelines

- Kubeflow Pipelines is the target orchestrator.
- Local pipeline components should still run as normal Python modules so development is not blocked by Kubernetes.
- Pipelines: data validation, VTON preprocessing, VTON training or fine-tuning, LLM quantization, evaluation, model registration, model promotion, scheduled retraining, and drift-triggered re-evaluation.

### Layer 5: Registry and Metadata

- MLflow Tracking for experiments.
- MLflow Model Registry for candidates, aliases, tags, lineage, and stage transitions.
- Artifact store for datasets, model weights, evaluation reports, generated images, quantized variants, model cards, and SBOMs.
- Metadata schema for every run: code version, data version, parameters, hardware, metrics, owner, approvals, risk status, and reproducibility command.

### Layer 6: Data Platform

- Raw, validated, processed, and feature/artifact zones.
- Dataset and large artifact versioning with DVC.
- MinIO as the local S3-compatible artifact store.
- Data contracts for person images, garment images, captions, masks, segmentation maps, prompts, calibration sets, and feedback records.
- Privacy controls for user-uploaded images and prompt data.

### Layer 7: Evaluation Platform

- VTON metrics: FID or KID, LPIPS, SSIM, CLIP similarity, garment fidelity, identity preservation, mask/segmentation consistency, human preference, artifact rate, latency, memory, and cost.
- LLM metrics: task accuracy, semantic similarity, hallucination checks, refusal behavior where relevant, latency, throughput, tokens/sec, memory, cost per 1k tokens, and quality regression.
- MLOps metrics: deployment frequency, lead time to promote a model, rollback time, failed release rate, reproducibility success, pipeline pass rate, incident count, and monitor coverage.

### Layer 8: Observability

- OpenTelemetry instrumentation for request traces.
- Prometheus-compatible metrics for service health, GPU memory, CPU memory, request latency, queue depth, errors, and throughput.
- ML monitors for data drift, input quality, output quality proxies, safety flags, feedback trends, and cost anomalies.
- Grafana dashboard for the live operational story.

### Layer 9: Governance and Risk

- Model cards for every promoted model.
- Data cards for every dataset.
- Approval gates before production promotion.
- Risk register mapped to NIST AI RMF categories.
- LLM security controls mapped to OWASP Top 10 for LLM Applications.
- Supply chain controls: pinned dependencies, SBOM, provenance, signed artifacts where practical, and vulnerability scanning.

### Layer 10: Infrastructure

- Local-first development with Docker Compose.
- Enterprise deployment profile with kind or k3d Kubernetes, Kubeflow Pipelines standalone, KServe, Prometheus, Grafana, and MinIO.
- GPU-aware containers where hardware is available.
- Infrastructure as code for repeatability.
- CI pipeline for lint, tests, build, artifact generation, and deployment checks.

## Locked Open-Source Technology Stack

This is the selected stack. Do not keep changing it unless evidence proves a component blocks the project.

### Core Language and ML

- Python: ML research, training/fine-tuning, evaluation scripts, Kubeflow components, MLflow glue, and experiment automation.
- Rust: target production API gateway using Axum/Tokio/Tower for request validation, timeouts, tracing, and high-concurrency service boundaries.
- Go: target Kubernetes/platform controller language for promotion reconciliation and deployment alias synchronization.
- C++: native policy/inference extension option; currently used for the verified dependency-free promotion policy module.
- PyTorch: VTON model execution and fine-tuning.
- Diffusers: diffusion-based VTON experimentation where compatible with selected models.
- Transformers: LLM loading, tokenization, and baseline inference.
- vLLM: primary optimized LLM serving engine.
- bitsandbytes, GPTQModel, AutoAWQ, or GGUF: quantization paths selected by hardware and model compatibility.

### MLOps Lifecycle

- Kubeflow Pipelines: enterprise-grade pipeline orchestrator and visual DAG.
- MLflow Tracking: experiment tracking.
- MLflow Model Registry: candidate, champion, challenger, rejected, and archived model lifecycle.
- DVC: dataset, benchmark set, and large artifact versioning.
- MinIO: local S3-compatible object store for datasets, artifacts, reports, generated samples, and SBOMs.
- PostgreSQL: metadata backend for MLflow and platform services where needed.

### Serving and Application

- Rust Axum gateway: target production front door.
- FastAPI: development control-plane fallback and lightweight local API skeleton.
- Go controller: target platform reconciler for model candidates, promotion decisions, and Kubernetes deployment aliases.
- vLLM OpenAI-compatible server: LLM serving.
- KServe: final enterprise inference deployment on Kubernetes.
- Triton and ONNX Runtime: stretch optimized serving paths for exported VTON or auxiliary models.
- Next.js or React: final polished professor-facing control room UI.
- Grafana: operational dashboards.

### Evaluation and Monitoring

- Evidently: data drift, data quality, LLM evaluation reports, and monitoring artifacts.
- Great Expectations: structured validation for dataset metadata and pipeline tables.
- Prometheus: metrics collection.
- OpenTelemetry: traces and logs correlation.
- Grafana: service, model, cost, and incident dashboards.

### Security, Governance, and Supply Chain

- OPA and Rego: policy-as-code for model promotion gates.
- Trivy: dependency, container, filesystem, secret, and configuration scanning.
- Syft: SBOM generation.
- Cosign: container and model artifact signing where feasible.
- Keycloak: identity provider for the enterprise demo if time allows; otherwise API-key auth with the Keycloak integration documented as future hardening.

### Infrastructure

- Docker Compose: local development and reliable demo fallback.
- kind or k3d: local Kubernetes cluster for enterprise deployment.
- Kubernetes manifests or Helm charts: repeatable service deployment.
- GitHub Actions or GitLab CI: CI/CD automation. If the project is not hosted remotely, mirror the same commands in a local `make ci` target.

### Deliberately Excluded From the Main Path

- Paid managed MLOps platforms: they reduce the open-source enterprise story.
- Full Kubeflow installation at the beginning: too heavy before the core pipelines are stable.
- TensorRT-LLM as a core requirement: valuable only if NVIDIA hardware is reliable; keep it as a benchmark appendix.
- Training a huge VTON model from scratch: not realistic and not the MLOps point.
- Building an agentic shopping assistant: tempting, but it dilutes the MLOps/VTON/optimization thesis.

## Opinionated Architecture Decisions

- Use MLOps maturity as the grading spine: every feature must support reproducibility, automation, governance, observability, reliability, or measurable optimization.
- Do not present Python as the final production boundary. Python is the ML lab layer; Rust, Go, C++, KServe, vLLM, Triton, and ONNX Runtime carry the production story.
- Start with Docker Compose, but design every service as if it will run on Kubernetes later.
- Use Kubeflow Pipelines for the final orchestrated ML workflow because it gives a visible enterprise DAG and artifact story.
- Use MLflow as the model registry because it is lightweight, clear, and professor-friendly.
- Use DVC instead of lakeFS for the main project because it is easier to explain, easier to run locally, and enough for image dataset versioning.
- Use KServe only after local serving is stable; KServe is the enterprise proof layer, not the first milestone.
- Use vLLM as the LLM optimization center because it gives a credible production serving story with batching, prefix caching, quantization support, and OpenAI-compatible APIs.
- Use CatVTON or IDM-VTON as the first VTON research target because they are recent, visually compelling, and aligned with diffusion-based VTON.
- Keep VITON-HD or HR-VITON as the classical baseline if the diffusion path becomes too heavy.
- Use policy-as-code for promotion gates: no model moves to champion unless tests, metrics, model card, data card, SBOM, and approval status pass.
- Treat every final demo output as an auditable artifact with lineage.

## Real Model Integration Plan (GPU-Backed)

This is the tranche that converts `[~]` contract-only items into `[x]` real evidence. Hardware: a CUDA GPU is available (`nvidia-smi`). The discipline: **the simulation spine never breaks** — real backends slot in behind the existing `/v1` contracts and pipeline interfaces, and every real component keeps a deterministic fallback so the demo survives a missing GPU, driver, or download. All ML/serving dependencies are already declared in `pyproject.toml` (`.[ml]`, `.[serving]`).

### R1: Real LLM Baseline (replace the deterministic stand-in)

- Load `SmolLM2-135M-Instruct` (and `Qwen2.5-0.5B/1.5B-Instruct` as a larger point) via Transformers behind the unchanged `/v1/llm/generate` schema.
- Record **real** latency, tokens/sec, peak VRAM, and quality on the existing golden prompt set; write to the same benchmark artifact shape so dashboards and gates need no change.
- Keep the deterministic baseline as the degraded-mode route via existing fallback routing.

### R2: Quantization Pareto Frontier (the optimization-rigor centerpiece)

- Build a quantization matrix over one base model: FP16 → bitsandbytes 8-bit → bitsandbytes 4-bit (NF4) → AWQ (INT4) → GPTQ (INT4) → GGUF (Q4_K_M via llama.cpp, CPU-first path) → vLLM (FP16 + AWQ).
- Hold the eval set, judge, and hardware fixed; report quality vs latency vs tokens/sec vs VRAM vs cost as a single Pareto chart with confidence intervals (multiple runs, report variance — statistical honesty is the differentiator).
- **Evaluation judge:** quality scoring uses a hybrid — the existing offline rubric (deterministic, always available) plus an optional LLM-as-judge using a Claude model (`claude-haiku-4-5` for cheap bulk scoring, `claude-opus-4-8` for tie-breaks/high-stakes pairs) via the Anthropic API. The judge is pinned, prompted with a rubric, and its verdicts are logged as artifacts so the comparison is auditable and reproducible; offline rubric is the fallback when no API key is present.

### R3: vLLM Production Serving Benchmark

- Stand up the vLLM OpenAI-compatible server; benchmark continuous batching and prefix caching at concurrency 1/4/16/32 against naive HF `generate`.
- This is the credible "production serving" story: PagedAttention, continuous batching, real throughput-under-load curves feeding the cost dashboard.

### R4: Real VTON

- Primary: **CatVTON** (chosen for lowest VRAM and minimal preprocessing — best fit for student hardware and reproducibility). Stretch: **IDM-VTON** for garment fidelity.
- Replace heuristic preprocessing with real adapters: SAM (mask), SCHP/DensePose (human parsing/pose), OpenPose (keypoints) — behind the existing C++ preprocessing CLI contract.
- Evaluate on a fixed 50-pair benchmark: FID/KID, LPIPS, SSIM, CLIP garment similarity, plus a 10–30 sample human-preference mini-study with a simple statistical summary. The local neural CLIP proof is now `make vton-clip-similarity-sample`; production evaluation still needs fixed-set CIs and pinned local model artifacts.

### R5: Make the Platform Backbone Real

- **MLflow:** point the registry/promotion path at a live MLflow tracking + Model Registry server (Docker Compose already declares it); log params/metrics/artifacts and drive champion/challenger aliases from real runs.
- **DVC + MinIO:** `make dvc-minio-sample` runs `dvc repro`, `dvc push`, and a native Go S3 verifier against MinIO; dataset/benchmark evidence is content-addressed and remotely present in `s3://tryops-artifacts/dvc`.
- **Compile the native boundary:** build and serve the Rust Axum gateway and Go controller in CI; wire the gateway in front of the FastAPI control plane and the controller to reconcile promotion aliases.

### Real-Tranche Acceptance

A real component is "done" only when: it runs on the GPU box, writes the **same artifact shape** the spine already consumes, is reproducible via a single `make` target, keeps a working degraded-mode fallback, and its run is logged to MLflow with full lineage.

## CI/CD and Supply Chain (Trust Pipeline)

This is the governance + supply-chain differentiator made executable. Every claim in the governance layer must be *enforced by automation*, not asserted in prose.

- **Pipeline (GitHub Actions, mirrored by `make ci` for offline/local hosting):** ruff lint → unit + integration tests → `make smoke` → build service images → **Syft** SBOM per image → **Trivy** vuln + secret + misconfig scan (fail on HIGH/CRITICAL) → **Cosign** sign images and candidate model packages → push → generate SLSA-style provenance attestation.
- **Gate consumption:** the OPA/Rego promotion policy already expects `signed`, SBOM, and scan fields — CI produces them for real, so a model with a missing signature, a missing SBOM, or an unresolved HIGH CVE is **rejected by policy**, not by a human. This closes the loop the Rust gateway preflight (`signed` check) and `tryops_policy` engine already model.
- **Evidence:** SBOM viewer + scan verdict + signature record attach to the model card and lineage, so "production-grade trust" is clickable, not claimed.
- **Pin everything:** lockfile, pinned model revisions (HF commit hashes) with recorded licenses, pinned base images by digest.

## Control Room UI (Product Polish)

One Next.js/React "mission control" surface that turns the whole platform into a 3-minute story for a professor and a 30-minute deep-dive for an examiner. Built **after** the spine is stable; every panel reads existing artifacts/APIs so it adds no new backend risk.

- **VTON Studio:** upload person + garment, side-by-side baseline vs candidate, with model version, latency, and quality metadata beside each output; thumbs feedback.
- **LLM Playground:** prompt box, variant selector (FP16 / INT8 / INT4 / AWQ / GGUF / vLLM), live latency/tokens-sec/VRAM/cost next to each response.
- **Lineage Viewer:** click any output → dataset version, model version, pipeline run, metrics, git commit, container digest, signature, approval record.
- **Champion/Challenger Board:** current production vs candidate with per-gate pass/fail and the promotion decision.
- **Pipeline Runs + Governance:** run history, evaluation report viewer, approval status, risk-control map.
- **Incident Console:** trigger the bad-deploy drill → alert → rollback → postmortem, live.
- **Embedded Grafana** panels + a **degraded-mode banner** that shows cached, lineage-backed outputs when the GPU is unavailable so the demo never fails.

## Brainstormed Wow Differentiators

Build these in priority order. The first eight are the strongest professor-facing differentiators.

1. Model lineage viewer: click a VTON output and see dataset version, model version, pipeline run, metrics, commit, container digest, and approval record.
2. Champion/challenger release board: compare current production model against a new candidate with pass/fail gates.
3. VTON failure gallery: automatically group bad outputs by issue type such as texture loss, sleeve distortion, identity shift, pose failure, and background artifacts.
4. LLM optimization Pareto dashboard: quality versus latency versus memory versus cost for FP16, INT8, INT4, GPTQ, AWQ, GGUF, and vLLM variants.
5. Policy-as-code promotion: OPA rejects a model if quality drops, latency is too high, model card is missing, SBOM is missing, or risk status is unresolved.
6. Shadow deployment simulation: new VTON or LLM model receives mirrored traffic and produces hidden evaluation results before promotion.
7. Drift-triggered re-evaluation: changed input image resolution, garment category, prompt length, or feedback score triggers an evaluation run.
8. Incident drill: intentionally deploy a bad candidate to staging, show alert, rollback, incident report, and postmortem.
9. Cost meter: estimate GPU seconds, memory footprint, and cost per 100 VTON generations and per 1M LLM tokens.
10. Risk dashboard: map NIST AI RMF and OWASP LLM risks to implemented controls.
11. Dataset quality score: show missing metadata, corrupt images, category imbalance, resolution spread, and duplicate rate.
12. Model cards generated by pipeline: not handwritten only; produced from tracked metrics and approval status.
13. Data cards generated by pipeline: dataset version, license, split statistics, limitations, and privacy notes.
14. Reproducibility badge: a run earns a badge only if data, code, environment, and artifact hashes are all present.
15. Signed artifacts: candidate model packages and containers have Cosign signatures.
16. SBOM viewer: inspect dependencies for each model service image.
17. Security scan gate: Trivy findings block promotion above a severity threshold.
18. Human preference mini-study: 10 to 30 comparisons of VTON outputs with simple statistical summary.
19. Prompt injection test suite: LLM service is tested against direct and indirect prompt injection examples.
20. Degraded-mode demo: if GPU is unavailable, the UI shows cached model outputs with authentic lineage and metrics.

## Wave 2 Brainstorm: Extended Research, Design, and Backlog

Date added: 2026-06-11. Wave 1 (the spine + R1/R2 real-model tranche) proves the platform works. Wave 2 is a prioritized set of *new* enterprise-MLOps capabilities that deepen the four winning differentiators — governance + supply chain, optimization rigor, product polish, platform breadth — and add two dimensions the field now expects: **sustainability** and **runtime AI safety**. Each theme follows the platform's discipline: a real backend behind an unchanged contract, a deterministic fallback, a `make` target, a JSON artifact the dashboards already consume, and (where the hot path is performance- or policy-critical) a **native C++ component**, since Python is the lab layer and compiled code carries the production boundary.

Themes are tagged by priority: **[P1]** highest leverage and feasible on the local L4 now; **[P2]** strong, do after P1.

### Theme M — Green MLOps: Energy and Carbon as First-Class Metrics [P1]

**Why enterprise:** sustainability reporting is now a board-level and regulatory concern, and no other student project will measure joules-per-inference. It also strengthens governance: a model that doubles energy for +0.5% quality should not promote.

**Design:** wrap each real inference (R1/R2/VTON) with a CodeCarbon-style sampler — `pynvml` for GPU power, Intel RAPL for CPU, integrated over wall-time — to emit a `tryops.energy.v1` artifact: `energy_wh`, `co2eq_g` (energy × grid carbon-intensity factor), `inferences_per_joule`, and `energy_delay_product` (EDP). The grid factor is a config value (documented assumption), so the metric is reproducible offline with a simulated power trace as the fallback. A new **native C++ `tryops_energy_stats`** engine aggregates the per-sample power trace into mean/peak watts, total kWh, and the Software Carbon Intensity (SCI) figure — same compiled-hot-path pattern as `tryops_perf_stats`. A **carbon-aware promotion gate** (OPA rule + the C++ policy engine) rejects a candidate whose energy-per-1k-tokens regresses beyond a threshold. New Grafana panel: energy + CO2e alongside latency/cost.

**First slice:** `make energy-sample` measures the R2 variants' real GPU energy and reports Wh-per-1k-tokens per quantization — a genuinely novel finding (4-bit's energy/throughput tradeoff), and the native engine emits the SCI verdict.

### Theme N — Rigorous Evaluation and LLM-as-Judge [P1]

**Why enterprise:** Wave 1 surfaced that the golden rubric was tuned to the deterministic baseline's exact wording (real models scored 0.25). Serious optimization claims need a *model-agnostic*, statistically honest evaluator — this is the optimization-rigor differentiator done right.

**Design:** (1) Replace exact-phrase rubric scoring with semantic + criteria scoring. (2) Add an **LLM-as-judge** using a Claude model through the Anthropic API: `claude-haiku-4-5` ($1/$5 per MTok) for cheap bulk pairwise/criterion scoring submitted via the **Batches API** (50% off, asynchronous — ideal for an eval sweep), with `claude-opus-4-8` reserved for low-agreement tie-breaks; judge calls use **structured outputs** (`output_config.format`) so every verdict is a validated JSON object, and each verdict is stored as an auditable artifact (pinned model id + prompt hash). (3) Add **statistical rigor**: bootstrap confidence intervals and a paired significance test on quality deltas between variants, plus judge-vs-rubric agreement (Cohen's κ) to calibrate trust. (4) An **eval leaderboard** artifact ranks every variant by quality CI, throughput, VRAM, energy, and SLO verdict. Offline rubric remains the deterministic fallback when no API key is present, so `make smoke` stays offline.

**First slice:** `make eval-judge-sample` re-scores the R2 Pareto variants with the Haiku judge + bootstrap CIs and writes a `tryops.eval_leaderboard.v1` artifact that the recommendation engine and UI consume.

### Theme O — GenAI Guardrails and LLM Security Runtime [P1]

**Why enterprise:** Wave 1 has prompt-injection *tests*; Wave 2 makes OWASP LLM Top-10 (2025) controls **enforced at runtime**, not just asserted. This is the security half of the governance differentiator.

**Design:** a guardrail layer in front of `/v1/llm/generate` mirroring the converged open-source stack — **Presidio** to redact PII at ingress (and re-insert at egress), a **Prompt-Guard / Llama-Guard**-style classifier for injection + output-safety (with a deterministic regex/keyword classifier as the offline fallback the spine already has), and a **schema validator** gating structured output. Map each control to an OWASP-LLM-2025 risk id (incl. the new entries — System Prompt Leakage, Excessive Agency, Unbounded Consumption) in a `tryops.guardrail_report.v1` artifact, and surface a "blocked requests by risk" Grafana panel. The guardrail verdict becomes a promotion-gate input (a model that leaks the system prompt cannot ship).

**First slice:** `make guardrail-sample` runs the existing `samples/security/*` cases plus PII and system-prompt-leak probes through the layer and reports per-OWASP-risk pass/block counts.

### Theme P — Trustworthy Model Supply Chain v2 [P1]

**Why enterprise:** extends the existing SBOM/Cosign story to the **model artifact itself**, the highest-risk and least-covered link. Pickle files are remote-code-execution vectors; picklescan itself had three CVSS-9.3 zero-day bypasses (JFrog, Dec 2025).

**Design:** (1) a **SafeTensors-only policy** — the promotion gate rejects any `.bin`/pickle model artifact. (2) A **model scan gate** running ModelScan / fickling (allowlist-based) over candidate weights, feeding the OPA/C++ policy. (3) **Sigstore model-signing** (the OpenSSF `model-transparency` project) to sign weights with keyless OIDC identity and verify at load, layered on the existing Cosign container signing. (4) **in-toto / SLSA provenance** attestation linking the released model back through pipeline run → commit → PR → human. Produces a `tryops.model_provenance.v1` artifact attached to the model card and lineage viewer.

**First slice:** `make model-supply-chain-sample` scans the candidate, asserts SafeTensors, emits a signed provenance attestation, and shows the OPA gate rejecting an unsigned/pickle candidate.

### Theme Q — FinOps and Semantic Caching [P2]

**Why enterprise:** turns the existing cost estimate into real unit economics with a budget control loop, plus a measurable cost-reduction lever.

**Design:** unit-economics artifact (cost per 1k tokens, per VTON, per active user using the documented hardware cost model), **budget gates** with burn alerts, and tenant **showback**. Add an **embedding-based semantic cache** in front of the LLM route (cosine-match recent prompts) and measure cache-hit rate and the cost/energy saved — the cache key/lookup hot path is a natural **native C++** component. Feeds the cost dashboard.

### Theme R — SRE for ML: SLOs, Error Budgets, and Chaos [P2]

**Why enterprise:** elevates the native `tryops_perf_stats` SLO engine into a full reliability story.

**Design:** formal SLOs with **error budgets** and **multi-window burn-rate alerts** (the Google SRE pattern) computed in the C++ engine; **chaos / failure injection** (simulate GPU OOM, slow decode, corrupted weights, a poisoned candidate) wired to the existing incident-drill; **auto-rollback when the burn rate crosses threshold**, closing the loop with the deployment/rollback artifacts already present.

### Theme S — GitOps Continuous Delivery and Lineage Standards [P2]

**Why enterprise:** interoperability and declarative deploy — what real platforms use.

**Design:** declarative deployment manifests reconciled GitOps-style (ArgoCD / Argo Rollouts canary), promotion via signed PR consumed by the Go controller, and **OpenLineage**-standard lineage emission (so the lineage graph speaks an industry schema, not just an internal JSON). Registry webhooks trigger deploy.

### Theme T — Online Experimentation [P2]

**Why enterprise:** extends champion/challenger into measured online decisions.

**Design:** A/B routing plus a **multi-armed-bandit** router that shifts traffic toward the better variant under guardrail metrics, with **sequential testing** (stop early when significant) and a holdback. Reuses the existing routing layer and the Theme-N significance machinery.

### Theme U — VTON Advanced Evaluation and Fairness [P2]

**Why enterprise:** domain depth + responsible AI for the CV workload.

**Design:** beyond FID/LPIPS — **identity preservation** via face-embedding distance, **garment-region-masked** fidelity metrics, **pose consistency**, and a **fairness audit** across skin-tone and body-type slices (a responsible-AI requirement), plus a **Bradley-Terry** model over the human-preference mini-study for a principled ranking. Feeds the model card's limitations and bias sections.

### Wave 2 Research Additions (living literature table)

- CodeCarbon — energy/CO2e tracking via pynvml + Intel RAPL, validated against external measurements (arXiv:2509.22092). URL: https://github.com/mlco2/codecarbon ; ground-truthing study: https://arxiv.org/html/2509.22092v1
- Software Carbon Intensity (SCI) specification — Green Software Foundation standard for per-unit carbon. URL: https://sci.greensoftware.foundation/
- LLM inference energy/carbon simulation and "inferences-per-joule" / Energy-Delay-Product metrics. URL: https://arxiv.org/html/2507.11417v1
- OWASP Top 10 for LLM Applications 2025 — adds System Prompt Leakage, Vector/Embedding Weaknesses, Excessive Agency, Unbounded Consumption, Misinformation. URL: https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf
- NVIDIA NeMo Guardrails — programmable dialog/jailbreak/injection guardrails. URL: https://github.com/NVIDIA-NeMo/Guardrails
- Meta Llama Guard 4 — multimodal input/output safety classifier (Apr 2025). URL: https://www.llama.com/
- Microsoft Presidio — PII detection and redaction. URL: https://github.com/microsoft/presidio
- Sigstore model-transparency / model-signing — keyless OIDC signing for ML weights (OpenSSF coalition, 2025). URL: https://github.com/sigstore/model-transparency ; Google rationale: https://security.googleblog.com/2025/04/taming-wild-west-of-ml-practical-model.html
- ModelScan (Protect AI) and fickling (Trail of Bits) — model-weight malware scanning; picklescan CVE bypasses motivate SafeTensors-only + allowlist scanning. URL: https://github.com/protectai/modelscan
- in-toto and SLSA — end-to-end pipeline attestation binding model → workflow → commit → human. URL: https://in-toto.io/ ; https://slsa.dev/
- OpenLineage — open standard for dataset/job/run lineage. URL: https://openlineage.io/
- Anthropic Claude API — LLM-as-judge models and economics: `claude-haiku-4-5` ($1/$5 per MTok) for bulk scoring via the Batches API (50% off), `claude-opus-4-8` for tie-breaks; structured outputs for validated JSON verdicts. URL: https://platform.claude.com/docs/

### Wave 2 Extended Backlog

New backlog sections, using the [Status Legend](#status-legend). These are design-ready; none are started unless marked.

#### M. Green MLOps (Energy and Carbon)

- [x] M001 Add a power sampler (`pynvml`/NVML) around real inference, with a deterministic simulated-trace fallback. (`src/tryops/energy.py`; real NVML verified on the L4.)
- [x] M002 Define the `tryops.energy.v1` artifact: energy_wh, co2eq_g, tokens_per_joule, energy_delay_product, SCI per 1k tokens.
- [x] M003 Build native C++ `tryops_energy_stats` to aggregate the power trace into mean/peak W, kWh, SCI, and a carbon-aware verdict (`make energy-demo-sample`; in `make smoke`).
- [x] M004 Make grid carbon-intensity a documented config value (default 475 gCO2e/kWh) recorded in the energy artifact.
- [x] M005 Measure real per-variant energy for the R2 quantization sweep (`make energy-sample`): Wh-per-1k-tokens + SCI per fp16/8-bit/4-bit variant.
- [x] M006 Add a carbon-aware promotion gate on energy-per-1k-tokens ceiling/regression (`carbon_aware_gate` + native engine verdict).
- [x] M007 Add an energy/CO2e Grafana panel and a cost-vs-energy correlation view. (`infra/grafana/dashboards/tryops-cost-capacity.json` now includes Energy per 1k Tokens, CO2e per 1k Tokens, and Cost vs Energy Correlation panels with Prometheus metric targets; `make dashboard-sample` validates the panels.)
- [x] M008 Write a sustainability section + estimation methodology (`docs/carbon_power_methodology.md`): NVML power → energy (mean W × duration) → carbon (energy_kWh × grid) → cost (× $/kWh and GPU $/hr), with worked examples and limitations. Report §16.4.

#### N. Rigorous Evaluation and LLM-as-Judge

- [x] N001 Replace exact-phrase rubric scoring with model-agnostic concept-coverage scoring. (`src/tryops/evaluation.py`; baseline answers rescored 0.25 → 0.83, fixing the documented rubric overfit.)
- [~] N002 Add a Claude LLM-as-judge: `claude-haiku-4-5` bulk, structured-output JSON verdicts. (`src/tryops/llm_judge.py` — wired via the Anthropic SDK with structured outputs; degrades to the offline rubric here as no `ANTHROPIC_API_KEY` is set. Batches-API path is the next step.)
- [~] N003 Add `claude-opus-4-8` tie-break path; pin model id + prompt hash per verdict. (Prompt fingerprint + model pinning implemented; tie-break routing pending a live key.)
- [x] N004 Add bootstrap confidence intervals and a paired significance test on variant quality deltas. (`evaluation.py` + native C++ `tryops_eval_stats`; `make eval-leaderboard-sample`.)
- [x] N005 Compute judge-vs-rubric agreement (Cohen's κ) to calibrate judge trust.
- [x] N006 Produce a `tryops.eval_leaderboard.v1` artifact ranking variants by quality CI / throughput / VRAM / energy / SLO. (`src/tryops/pipelines/eval_leaderboard.py`; in `make smoke`.)
- [x] N007 Keep the offline rubric as the deterministic fallback so `make smoke` stays offline.
- [x] N008 Wire the leaderboard into the recommendation engine and the control-room UI. (`native/go/tryops-evaluation-index` now combines Pareto, leaderboard, and energy evidence into `optimization_panel`; `web/src/components/EvaluationView.tsx` renders the ranked variants, recommendation, judge backend, and energy/SCI metrics; `make app-smoke` proves the payload through the Rust gateway.)

#### O. GenAI Guardrails and LLM Security Runtime

- [x] O001 Add a Presidio-style PII redact-at-ingress / re-insert-at-egress wrapper for `/v1/llm/generate`. (`src/tryops/guardrails.py` redacts PII-like inputs before generation, restores scoped placeholders at egress, and never exposes raw PII in public verdicts.)
- [x] O002 Add an injection + output-safety classifier (Prompt-Guard/Llama-Guard) with the deterministic fallback. (`native/go/tryops-guardrail` is split into server, CLI, evaluator, metrics, and contract modules; it provides a Go sidecar/CLI for prompt injection, system-prompt leakage, secret disclosure, unbounded consumption, unsafe agency, and output leakage; Python fallback keeps offline smoke deterministic.)
- [x] O003 Add a structured-output schema validator gate. (`validate_structured_output` blocks malformed `structured_answer` payloads on egress.)
- [x] O004 Map every control to an OWASP-LLM-2025 risk id, including the 2025 additions. (`configs/governance_risk_controls.json` and `tryops.guardrail_verdict.v1` map controls to LLM01, LLM02, LLM05, LLM06, LLM07, and LLM10, while governance keeps all ten OWASP IDs covered.)
- [x] O005 Emit a `tryops.guardrail_report.v1` artifact and a "blocked-by-risk" Grafana panel. (`make guardrail-sample` writes `artifacts/eval/guardrails/guardrail_report.json`; `infra/grafana/dashboards/tryops-guardrails.json` targets guardrail risk counters.)
- [x] O006 Make the guardrail verdict (e.g., system-prompt-leak) a promotion-gate input. (`configs/promotion_policy.json` and `src/tryops/policy.py` require LLM candidates to include a passing guardrail report with zero failed cases.)
- [x] O007 Add system-prompt-leakage and unbounded-consumption probes to the security sample set. (`samples/security/llm_security_cases.json` plus built-in evaluator probes cover LLM07 and LLM10.)

#### P. Trustworthy Model Supply Chain v2

- [x] P001 Enforce a SafeTensors-only policy; reject pickle/`.bin` model artifacts at the gate. (`native/cpp/tryops_model_scan` validates `.safetensors` headers and rejects pickle-family weight extensions before promotion.)
- [x] P002 Add a model-weight scan gate (ModelScan / fickling allowlist) feeding OPA + the C++ policy. (`tryops.native_model_scan.v1` feeds `src/tryops/policy.py`, `native/cpp/tryops_policy`, and `policies/model_promotion.rego`; `make model-supply-chain-sample` proves Python/native decisions match.)
- [~] P003 Sign model weights with Sigstore model-transparency (keyless OIDC) and verify at load. (Local DSSE-shaped model signature bundle and native C++ load-time verifier are implemented; real Sigstore keyless OIDC/Rekor evidence remains production hardening.)
- [~] P004 Emit an in-toto / SLSA provenance attestation linking model → run → commit → PR → human. (`model_provenance.intoto.json` uses `https://slsa.dev/provenance/v1` and links model → run → source commit → human approver; real PR identity is unavailable in this non-git local workspace.)
- [x] P005 Produce `tryops.model_provenance.v1`; attach to the model card and lineage viewer. (`make model-supply-chain-sample` writes `artifacts/eval/model_supply_chain/model_provenance.json`; model cards list `model_provenance`; lineage now exposes a dedicated provenance block.)
- [x] P006 Demo the gate rejecting an unsigned or pickle candidate (`make model-supply-chain-sample`). (`artifacts/eval/model_supply_chain/model_supply_chain_report.json` contains safe and unsafe candidate decisions; the unsafe `.bin` candidate is rejected by Python and native C++.)

#### Q. FinOps and Semantic Caching

- [x] Q001 Produce a unit-economics artifact (cost per 1k tokens / per VTON / per active user). (`make finops-sample` writes `tryops.unit_economics.v1` under `artifacts/eval/finops/` using the open-source self-hosted hardware run-rate model.)
- [x] Q002 Add budget gates with burn alerts and per-tenant showback. (`tryops.budget_showback.v1`, `infra/prometheus/tryops_finops_alerts.yml`, and the Compose Prometheus rule mount cover warning/hard-limit budget gates.)
- [x] Q003 Add an embedding-based semantic cache in front of the LLM route. (`/v1/llm/generate` now runs a privacy-aware semantic-cache lookup after guardrails/quota and before generation; PII-redacted prompts are not stored.)
- [x] Q004 Implement the cache key/lookup hot path as a native C++ component. (`native/cpp/tryops_semantic_cache` is split into reusable C++ core header/source, thin CLI adapter, and native tests; it emits `tryops.native_semantic_cache.v1`; Python falls back only when the binary is absent.)
- [x] Q005 Measure cache-hit rate and cost/energy saved; add to the cost dashboard. (`tryops.semantic_cache_report.v1` records hit rate, tokens, cost, and energy saved; `tryops-cost-capacity` now has cache hit/savings and budget-utilization panels.)

#### R. SRE for ML: SLOs, Error Budgets, Chaos

- [x] R001 Define formal SLOs with error budgets per workload. (`configs/service_level_objectives.json` defines LLM, VTON, and control-plane objectives, 30-day budgets, and multi-window policy.)
- [x] R002 Compute multi-window burn-rate alerts in the native C++ engine. (`tryops_burn_rate_cli` evaluates page/ticket long+short windows and writes `tryops.slo_burn_rate_report.v1` via `make slo-burn-rate-sample`.)
- [x] R003 Add chaos/failure injection (GPU OOM, slow decode, corrupted weights, poisoned candidate). (`native/cpp/tryops_chaos` classifies deterministic fault scenarios and `make chaos-sample` writes `tryops.chaos_drill_report.v1`.)
- [x] R004 Auto-rollback when the burn rate crosses threshold, reusing the rollback artifacts. (`make chaos-sample` feeds each injected fault into the native C++ burn-rate engine and records `auto_rollback_record.json` plus `rollback_state.json` when page burn-rate thresholds fire.)

#### S. GitOps CD and Lineage Standards

- [x] S001 Add declarative deployment manifests reconciled GitOps-style (ArgoCD / Argo Rollouts canary). (`make deploy-package-sample` writes `gitops/application.yaml`, `rollout.yaml`, `services.yaml`, and `kustomization.yaml`; native C++ `tryops_gitops` validates the Argo CD Application and Argo Rollouts canary structure.)
- [x] S002 Promote via signed PR consumed by the Go controller. (`make signed-pr-promotion-sample` starts the modular Go controller, sends a GitHub-style signed `pull_request.closed` webhook with merged PR, code-owner approval, verified commit, status checks, promotion/OpenLineage/GitOps/provenance evidence, and returns champion promotion plus registry-alias sync actions; report: `artifacts/eval/signed_pr/signed_pr_promotion_report.json`.)
- [x] S003 Emit OpenLineage-standard lineage events alongside the internal JSON. (`reports/generated/.../openlineage_run_event.json` maps TryOps promotion lineage to an OpenLineage RunEvent with job/run/input/output datasets; `tryops_openlineage_cli` emits `tryops.native_openlineage.v1` validation evidence.)
- [x] S004 Trigger deploy from registry webhooks. (`make registry-webhook-sample` starts the modular Go controller, sends a signed MLflow-style `model_version_alias.created` webhook, verifies HMAC freshness/signature headers, and returns GitOps sync plus Argo Rollouts canary actions; report: `artifacts/eval/registry_webhook/registry_webhook_report.json`.)

#### T. Online Experimentation

- [x] T001 Add A/B routing with guardrail metrics over the existing routing layer. (`build_experiment_routing_decision` delegates A/B allocation and guardrail eligibility to native C++ `tryops_experiment_router`; `make experiment-routing-sample` writes `artifacts/eval/experiments/online_experiment_report.json`.)
- [x] T002 Add a multi-armed-bandit router that shifts traffic toward the better variant. (`tryops_experiment_router` computes guarded UCB-style scores in C++, blocks the guardrail-violating candidate, and shifts/serves traffic to the higher-performing challenger in the sample report.)
- [x] T003 Add sequential testing (early stop on significance) reusing the Theme-N machinery. (`native/cpp/tryops_experiment_stats` computes Wald-style SPRT early-stop verdicts, and `make experiment-analysis-sample` reuses native `tryops_eval_stats` for a Theme-N bootstrap delta CI.)
- [x] T004 Add a holdback group and report uplift with confidence intervals. (`make experiment-analysis-sample` writes `artifacts/eval/experiments/online_experiment_analysis_report.json` with a `champion_holdback` group, Agresti-Caffo uplift CIs, and challenger uplift/early-stop evidence.)

#### U. VTON Advanced Evaluation and Fairness

- [x] U001 Add identity-preservation scoring via face-embedding distance. (`native/cpp/tryops_vton_eval` emits a native face-region embedding-proxy distance and score in `artifacts/eval/vton_advanced/vton_advanced_eval_report.json`; production neural ArcFace/InsightFace is documented as the replacement target.)
- [x] U002 Add garment-region-masked fidelity metrics and pose-consistency checks. (`tryops_vton_eval` computes masked patch MSE/PSNR/dHash/edge fidelity and torso-alignment pose consistency from the VTON overlay region via `make vton-advanced-eval-sample`.)
- [x] U003 Add a fairness audit across skin-tone and body-type slices. (`samples/eval/vton_preference_study.json` carries seeded slice rows; the native evaluator computes skin-tone/body-type quality gaps and threshold pass/fail evidence.)
- [x] U004 Fit a Bradley-Terry model over the human-preference study for a principled ranking. (`tryops_vton_eval` fits a Bradley-Terry MM ranking over the seeded preference-study fixture and records strengths plus winner in the advanced eval report.)
- [x] U005 Feed results into the model card's limitations and bias sections. (`scripts/evaluate_vton_advanced.py` updates `reports/generated/vton-catvton-2026-06-11-001/model_card.md` with the advanced VTON evaluation, fairness gaps, Bradley-Terry winner, and bias/limitation notes.)

## Evaluation Scorecard

### Professor Wow Criteria

- End-to-end automation: every important step can run from a pipeline, not only a notebook.
- Lineage: every model output can be traced to code, data, config, run, artifact, and metrics.
- Comparison: baseline and optimized models are compared with clear evidence.
- Governance: promotion requires policy gates and produces model/data cards.
- Observability: the system shows live service and model health.
- Reliability: failures are handled with retry, rollback, fallback model, and incident notes.
- Performance: LLM optimization demonstrates real memory, latency, throughput, or cost gains.
- Domain value: VTON is visually compelling and evaluated with meaningful metrics.
- Communication: the final report explains tradeoffs like an ML platform engineer, not only a model trainer.

### Must-Have Metrics

- VTON p50 and p95 latency.
- VTON GPU or CPU memory per request.
- VTON output quality metrics and human evaluation table.
- VTON garment fidelity score or proxy.
- LLM tokens/sec.
- LLM p50 and p95 latency.
- LLM memory footprint by precision or quantization method.
- LLM quality score before and after quantization.
- Pipeline success rate.
- Reproducibility pass rate.
- Model registry promotion history.
- Monitoring alert count and sample incident response.
- Cost per 100 VTON requests and cost per 1M LLM tokens using a documented local hardware cost estimate.

## Month-by-Month Roadmap

### Month 1: Research, Scope, and Requirements

Goal: define the project like a product and research platform before writing too much code.

Deliverables:

- Problem statement.
- Architecture decision records.
- Literature review table.
- Dataset and model candidate comparison.
- MLOps maturity target.
- Risk register version 1.
- Demo storyboard version 1.

Gate:

- You can explain why MLOps is the core and why VTON/LLM are workloads.
- You have chosen the minimum viable stack and stretch stack.
- You have success metrics for every major subsystem.

### Month 2: Architecture and Data Foundation

Goal: create the project skeleton, data contracts, artifact layout, reproducibility rules, and baseline UI/API boundaries.

Deliverables:

- Repository structure.
- Docker development environment.
- Dataset ingestion pipeline.
- Data validation report.
- Artifact storage layout.
- MLflow tracking server.
- Baseline FastAPI endpoints.
- Basic UI skeleton.

Gate:

- A fresh machine can run the skeleton.
- A sample data pipeline produces versioned artifacts.
- Experiments are tracked with metadata.

### Month 3: Baseline MLOps Pipeline

Goal: prove the operating system before chasing model quality.

Deliverables:

- First orchestrated pipeline.
- Evaluation report generator.
- Model registry workflow.
- Model card template.
- Promotion gate version 1.
- CI checks.
- Basic observability.

Gate:

- A toy model can go from data to registry to serving through the pipeline.
- A failed quality gate prevents promotion.
- A dashboard shows basic service metrics.

### Month 4: VTON Baseline and Evaluation Harness

Goal: make the VTON workload real and measurable.

Deliverables:

- VTON dataset subset.
- Baseline VTON inference.
- Preprocessing pipeline for person/garment images.
- VTON evaluation suite.
- Human evaluation rubric.
- Before/after comparison UI.
- Model lineage for generated images.

Gate:

- You can run VTON on a repeatable test set.
- You can compare at least two methods or configurations.
- You can explain visual failures with evidence.

### Month 5: LLM Quantization and Serving Optimization

Goal: make optimization measurable, not just theoretical.

Deliverables:

- Baseline open-source LLM service.
- Quantized variants using feasible methods such as bitsandbytes, GPTQ, AWQ, GGUF, or FP8 where hardware supports it.
- vLLM serving benchmark.
- Latency, throughput, memory, and quality comparison.
- LLM safety and security checklist.
- Model routing between variants.

Gate:

- At least one optimized model improves memory, latency, throughput, or cost while preserving acceptable quality.
- The benchmark is reproducible.
- Results are visible in the dashboard and report.

### Month 6: Enterprise Hardening

Goal: add the pieces that make the project feel production-grade.

Deliverables:

- Auth or API key simulation.
- Rate limiting and payload validation.
- Audit logs.
- SBOM and dependency scan.
- Governance approval workflow.
- Drift and quality monitors.
- Rollback playbook.
- Incident response template.

Gate:

- A risky model cannot be promoted without an explicit approval.
- The system can simulate an alert, incident, and rollback.
- Security risks are mapped to controls.

### Month 7: Continuous Improvement Loops

Goal: close the loop from production feedback to retraining or re-optimization.

Deliverables:

- Feedback capture pipeline.
- Drift-triggered retraining or re-evaluation.
- Scheduled benchmark jobs.
- Candidate/champion comparison.
- Canary or shadow release simulation.
- Error analysis dashboard.

Gate:

- The system can detect a simulated issue and create a candidate improvement run.
- The model registry clearly distinguishes champion, challenger, archived, and rejected models.

### Month 8: Polish, Final Evaluation, and Story

Goal: turn the platform into a compelling thesis-quality artifact.

Deliverables:

- Final architecture diagram.
- Final demo script.
- Final report draft.
- Experiment result tables.
- Dashboard cleanup.
- Reproducibility guide.
- Video walkthrough draft.

Gate:

- A professor can understand the system in 3 minutes and inspect depth for 30 minutes.
- Metrics prove improvement and operational maturity.

### Month 9: Buffer, Defense, and Excellence Pass

Goal: fix weak links, improve reliability, and prepare for questions.

Deliverables:

- Final bug fixes.
- Stress tests.
- Failure injection demo.
- Backup demo path.
- Final slides.
- Final report.
- Defense Q&A.
- Future work roadmap.

Gate:

- You can run the demo offline or with degraded dependencies.
- You can answer architecture, research, risk, and evaluation questions with evidence.

## Master Action Backlog: 240 Items

Items use the [Status Legend](#status-legend): `[x]` done & real, `[~]` contract-only / simulated (real backend pending), `[ ]` not started. Every `[~]` item is closed by the [Real Model Integration Plan (GPU-Backed)](#real-model-integration-plan-gpu-backed) or the [CI/CD and Supply Chain](#cicd-and-supply-chain-trust-pipeline) tranche. When a checkbox and the code disagree, `docs/roadmap_audit.md` wins.

### A. Research Framing and Literature Review

- [x] A001 Define the one-sentence thesis: "MLOps platform for governed VTON and efficient LLM serving."
- [x] A002 Write a one-page project charter with motivation, scope, users, and expected impact.
- [x] A003 Create a literature spreadsheet for MLOps, VTON, LLM quantization, serving, monitoring, and AI governance.
- [x] A004 Summarize Google MLOps maturity levels and extract platform requirements.
- [x] A005 Summarize Azure MLOps maturity level 4 and map it to your target architecture.
- [x] A006 Summarize MLflow registry capabilities and decide the metadata fields your registry must store.
- [x] A007 Read Hidden Technical Debt in ML Systems and list the technical debt risks your project must prevent.
- [x] A008 Read VITON-HD and identify its preprocessing, warping, and quality evaluation assumptions.
- [x] A009 Read Dress Code and decide whether multi-category garments are in or out of scope.
- [x] A010 Read HR-VITON and list common VTON failures around occlusion and misalignment.
- [x] A011 Read StableVITON and extract diffusion-specific VTON evaluation ideas.
- [x] A012 Read IDM-VTON and summarize how garment fidelity is improved.
- [x] A013 Read FLDM-VTON and capture the idea of faithful garment priors.
- [x] A014 Read CatVTON and record why simpler preprocessing may matter for MLOps.
- [x] A015 Read GPTQ and note calibration, bit width, speed, and quality tradeoffs.
- [x] A016 Read SmoothQuant and note when W8A8 matters compared with weight-only quantization.
- [x] A017 Read AWQ and summarize activation-aware salient channel protection.
- [x] A018 Read FlashAttention and explain IO-aware attention in simple terms for your report.
- [x] A019 Read vLLM docs and list serving features relevant to your benchmark.
- [x] A020 Read TensorRT-LLM docs and decide whether your available hardware justifies a stretch implementation.

### B. Enterprise Architecture and System Design

- [x] B001 Draw the first C4 context diagram for users, UI, APIs, pipelines, registry, storage, and monitors.
- [x] B002 Draw the container diagram for VTON service, LLM service, orchestrator, registry, artifact store, and dashboard.
- [x] B003 Define environment boundaries for local, development, staging, and production-demo.
- [x] B004 Create architecture decision record 001 for local-first versus cloud-first implementation.
- [x] B005 Create architecture decision record 002 confirming Kubeflow Pipelines as the orchestrator.
- [x] B006 Create architecture decision record 003 for model registry choice.
- [x] B007 Create architecture decision record 004 for VTON baseline model choice.
- [x] B008 Create architecture decision record 005 for LLM base model choice.
- [x] B009 Define service-level objectives for VTON latency, availability, and failure handling.
- [x] B010 Define service-level objectives for LLM latency, throughput, and memory.
- [x] B011 Define data zones: raw, validated, processed, benchmark, production-feedback, and archived.
- [x] B012 Define artifact zones: models, reports, generated samples, logs, cards, and deployment packages.
- [x] B013 Design request and response schemas for VTON inference.
- [x] B014 Design request and response schemas for LLM inference.
- [x] B015 Design a metadata schema for model registry entries.
- [x] B016 Design a policy gate schema for model promotion.
- [x] B017 Design a feedback schema for user ratings and failure labels.
- [x] B018 Design the dashboard information architecture.
- [x] B019 Design a rollback and fallback architecture.
- [x] B020 Review the architecture with the question: "What would break first in production?"

### C. Data Governance, Dataset Engineering, and Privacy

- [x] C001 Inventory all candidate datasets and record license, size, resolution, garment categories, and access constraints.
- [x] C002 Select the smallest dataset subset that supports a reliable demo.
- [x] C003 Document excluded data and why it is excluded.
- [x] C004 Create data card template version 1.
- [x] C005 Create data ingestion script or pipeline step.
- [x] C006 Add dataset checksum generation.
- [x] C007 Add schema validation for metadata files.
- [x] C008 Add image validation for file type, dimensions, color mode, and corrupted files.
- [x] C009 Add duplicate detection for images where feasible.
- [x] C010 Add train, validation, test, and demo split rules.
- [x] C011 Create a calibration set for LLM quantization.
- [x] C012 Create a golden prompt set for LLM quality testing.
- [x] C013 Create a golden image pair set for VTON quality testing.
- [x] C014 Define privacy rules for uploaded person images.
- [x] C015 Define retention rules for generated outputs.
- [x] C016 Add synthetic or public-only demo data to avoid private image risk.
- [x] C017 Version the dataset with DVC and store large artifacts in MinIO. (`dvc.lock` now pins the promotion evidence stage and `make dvc-minio-sample` verifies 12 local DVC cache objects pushed to MinIO with `tryops.dvc_minio_versioning.v1`.)
- [x] C018 Store dataset lineage in experiment metadata.
- [x] C019 Add a data quality report to every training or evaluation run.
- [x] C020 Write a data governance section for the final report.

### D. VTON Modeling and Evaluation

- [x] D001 Implement or integrate the simplest VTON baseline that can run on available hardware. (Plus a **real** diffusion try-on: SD1.5 inpainting on CUDA, `make vton-real-sample`, deterministic fallback.)
- [x] D002 Create a baseline inference notebook only for exploration, not as the production path.
- [x] D003 Convert VTON inference into a callable Python module.
- [x] D004 Wrap VTON inference behind a FastAPI endpoint.
- [x] D005 Create preprocessing for person image normalization.
- [x] D006 Create preprocessing for garment image normalization.
- [x] D007 Add optional segmentation or mask preprocessing if the selected model needs it.
- [x] D008 Add optional pose preprocessing if the selected model needs it.
- [x] D009 Cache expensive preprocessing artifacts.
- [x] D010 Build a fixed VTON benchmark set.
- [x] D011 Implement LPIPS or another perceptual similarity metric if dependencies allow.
- [x] D012 Implement SSIM or a simpler structural metric for paired evaluation.
- [x] D013 Implement CLIP-based garment-text or garment-image similarity if feasible. (`make vton-clip-similarity-sample` runs the Transformers CLIP backend with `openai/clip-vit-base-patch32` on CPU and writes `artifacts/eval/vton_clip/garment_clip_similarity.json`; the evaluation index surfaces it as `vton_clip`.)
- [x] D014 Implement latency and memory measurement for VTON inference.
- [x] D015 Create a human evaluation rubric for realism, garment fidelity, identity preservation, and artifacts.
- [x] D016 Compare at least two VTON configurations or models.
- [x] D017 Generate an error gallery with categories like sleeve failure, texture loss, identity distortion, and background artifacts.
- [x] D018 Add VTON output lineage links from generated image to model version and dataset version.
- [x] D019 Add VTON safety checks for invalid, oversized, or unsupported images.
- [x] D020 Write a VTON results section with strengths, failures, and future work.

### E. LLM Quantization, Acceleration, and Serving

- [x] E001 Choose a small base LLM that can run on available hardware.
- [x] E002 Define the LLM workload: project assistant, product explainer, evaluator, or retrieval helper.
- [x] E003 Create baseline LLM inference script.
- [x] E004 Add a FastAPI route for LLM inference.
- [x] E005 Create a golden prompt set with expected characteristics, not only exact answers.
- [x] E006 Measure baseline latency, tokens/sec, memory, and output quality. (R1 done: real SmolLM2-135M on CUDA, ~18.5 tok/s, 0.28 GB VRAM via `make llm-real-sample`; deterministic baseline retained as fallback.)
- [x] E007 Test bitsandbytes 8-bit or 4-bit loading if CUDA and dependencies support it. (R2 done: real 8-bit + 4-bit NF4 of Qwen2.5-0.5B on CUDA via `make llm-pareto-sample`.)
- [~] E008 Test GPTQ model loading if a suitable quantized model is available. (Native Go preflight verifies `Qwen/Qwen2.5-0.5B-Instruct-GPTQ-Int4`: reachable config, `quant_method=gptq`, 4-bit, group size 128, SafeTensors artifact reachable; live loading is blocked locally because `gptqmodel` / `auto_gptq` are absent.)
- [~] E009 Test AWQ model loading if a suitable quantized model is available. (Native Go preflight verifies `Qwen/Qwen2.5-0.5B-Instruct-AWQ`: reachable config, `quant_method=awq`, 4-bit, group size 128, GEMM/zero-point config, SafeTensors artifact reachable; live loading is blocked locally because `awq` / `autoawq` are absent.)
- [x] E010 Test GGUF or llama.cpp path if CPU-first deployment is needed. (Native C++ GGUF preflight parses a real `SmolLM2-135M-Instruct-Q2_K.gguf` artifact via `make llm-gguf-preflight-sample`; `llama-cli` is not installed here, so live generation remains a follow-up.)
- [~] E011 Test vLLM serving on the selected model if hardware supports it. (Native Go harness added via `make llm-vllm-probe-sample`; it checks `/v1/models`, `/v1/chat/completions`, `/metrics`, GPU presence, and load latency. Current local evidence is `status=skipped` because `vllm` is not installed and no vLLM endpoint is serving on `127.0.0.1:8000`; live benchmark remains open.)
- [x] E012 Benchmark continuous batching with multiple concurrent requests. (`tryops_batch_scheduler` compares request-level static batching with iteration-level continuous batching in native C++ over a 20-request mixed prompt/decode workload via `make llm-continuous-batching-sample`; current evidence: 1.218x modeled throughput, 19.1% p95 latency reduction, decode-slot utilization 0.623 -> 1.0. This is scheduler evidence, not live vLLM serving; E011 remains open.)
- [x] E013 Benchmark prompt length sensitivity.
- [x] E014 Benchmark output length sensitivity.
- [x] E015 Measure memory footprint for each variant. (R2: peak `torch.cuda` VRAM per variant — fp16 1.01 GB, 8-bit 0.65 GB, 4-bit 0.48 GB.)
- [x] E016 Compare quality regressions across quantization variants. (R2: rubric quality + native C++ SLO verdict per variant; 8-bit flagged dominated.)
- [x] E017 Add fallback routing from optimized model to baseline model.
- [x] E018 Add structured JSON output mode where useful for evaluations.
- [x] E019 Add cost estimates per request or per 1k tokens.
- [x] E020 Write an LLM optimization report with a quality-latency-memory Pareto chart. (R2 report generated from `tryops.llm_pareto.v1`: Markdown + SVG chart + CSV + audit JSON via `make llm-optimization-report-sample`.)

### F. Pipelines, Automation, and Reproducibility

- [x] F001 Set up the project with a reproducible environment file.
- [x] F002 Add Dockerfile for API services.
- [x] F003 Add Docker Compose for local platform services.
- [~] F004 Add MLflow tracking service. (Compose now builds a working MLflow image with PostgreSQL/S3 dependencies and `make app-smoke` verifies `/health` inside a disposable smoke project with fresh volumes; live run/registry writes land in R5.)
- [x] F005 Add artifact storage path or MinIO service. (MinIO starts in Compose, `make app-smoke` verifies readiness, and `make dvc-minio-sample` proves `dvc push` to the MinIO bucket.)
- [x] F006 Add orchestration framework skeleton.
- [x] F007 Build a data validation pipeline.
- [x] F008 Build a VTON evaluation pipeline.
- [x] F009 Build an LLM quantization benchmark pipeline.
- [x] F010 Build a model registration pipeline.
- [x] F011 Build a model promotion pipeline.
- [x] F012 Build a deployment packaging pipeline.
- [x] F013 Add pipeline parameters through config files.
- [x] F014 Add run IDs and trace IDs across pipeline logs.
- [x] F015 Store git commit or code version in every run where possible.
- [x] F016 Store dataset version in every run.
- [x] F017 Store environment details and hardware details in every run.
- [x] F018 Add one-command local reproduction for the main demo.
- [x] F019 Add one-command benchmark reproduction.
- [x] F020 Add a reproducibility checklist to the final report.

### G. Serving, APIs, and Release Engineering

- [x] G001 Define API versioning rules.
- [x] G002 Add health check endpoints.
- [x] G003 Add readiness endpoints for model-loaded state.
- [x] G004 Add structured request validation.
- [x] G005 Add structured error responses.
- [x] G006 Add request ID propagation.
- [x] G007 Add file size limits for image uploads.
- [x] G008 Add timeout handling for long inference calls.
- [x] G009 Add async job mode for VTON generation if synchronous inference is slow.
- [x] G010 Add model selection through safe aliases rather than raw paths.
- [x] G011 Add champion/challenger routing.
- [x] G012 Add canary routing simulation.
- [x] G013 Add shadow evaluation mode.
- [x] G014 Add a staging deployment profile.
- [x] G015 Add a production-demo deployment profile.
- [x] G016 Add rollback command or documented rollback procedure.
- [x] G017 Add smoke tests for deployed VTON endpoint.
- [x] G018 Add smoke tests for deployed LLM endpoint.
- [x] G019 Add load test script for concurrent LLM requests.
- [x] G020 Add release notes for every model promotion.
- [x] G021 Add usage-based quota enforcement for LLM and VTON requests. (`tryops-gateway` now owns the native Rust quota endpoint/CLI, `make quota-sample` emits Rust-backed hashed usage evidence, and Python delegates to `TRYOPS_QUOTA_GATEWAY_URL` when the gateway is present.)
- [x] G022 Expose quota decisions and quota-exceeded errors in API responses. (`/v1/quota/check` returns `tryops.quota_decision.v1` with per-dimension used/remaining capacity and quota-exceeded verdicts; `/v1/llm/generate` and `/v1/vton/infer` keep the same response contract.)

### H. Observability, Monitoring, and Feedback Loops

- [x] H001 Instrument API request latency.
- [x] H002 Instrument API error rate.
- [x] H003 Instrument request payload metadata without storing unsafe personal content.
- [x] H004 Instrument model version per request.
- [x] H005 Instrument VTON generation duration by stage.
- [x] H006 Instrument LLM prefill and decode timing if available. (`tryops.llm_phase_timing.v1` now appears in LLM responses, benchmark records, structured logs, and Prometheus phase metrics.)
- [x] H007 Instrument tokens/sec for LLM outputs. (`native/go/tryops-runtime-telemetry/` exports real benchmark and Pareto tokens/sec into `tryops.native_runtime_telemetry.v1` plus Prometheus text; `artifacts/eval/runtime/native_runtime_telemetry.prom` includes `tryops_llm_tokens_per_second` for baseline and variants.)
- [x] H008 Instrument GPU memory or CPU memory. (`native/go/tryops-runtime-telemetry/` queries `nvidia-smi` for live GPU memory/utilization/power, records the NVIDIA L4 snapshot in `artifacts/eval/runtime/native_runtime_telemetry.json`, and emits `tryops_gpu_memory_used_bytes`, `tryops_gpu_memory_total_bytes`, `tryops_gpu_utilization_ratio`, and `tryops_gpu_power_watts`.)
- [x] H009 Instrument queue depth for async jobs.
- [x] H010 Add structured application logs.
- [x] H011 Add OpenTelemetry tracing where practical. (`tryops.trace_span.v1` emits W3C-compatible trace/span IDs, `traceparent` propagation, sanitized JSONL spans, structured-log correlation, API response trace context, and Prometheus trace metrics.)
- [x] H012 Create Grafana service dashboard.
- [~] H013 Create model-quality dashboard. (Grafana JSON provisioned; needs a live quality exporter in R5.)
- [~] H014 Create cost dashboard or cost estimate table. (Provisioned; needs a live cost exporter in R5.)
- [~] H015 Create drift report for image metadata distributions. (Contract + report real; current window is simulated until live-traffic windows in R5.)
- [~] H016 Create drift report for prompt length and topic distributions. (Contract + report real; current window simulated until R5.)
- [x] H017 Add alert thresholds for latency regression.
- [x] H018 Add alert thresholds for quality regression.
- [x] H019 Add feedback collection in the UI. (`web/src/components/LlmPlayground.tsx` posts ratings/comments to `POST /api/feedback`; dashboard refresh shows persisted feedback rollups.)
- [~] H020 Add a feedback-to-retraining or feedback-to-review workflow. (Feedback now persists through the product UI and audit path; a reviewer queue/retraining handoff remains.)
- [x] H021 Add quota-safe user usage metadata without storing raw user IDs.

### I. Testing, Benchmarking, and Quality Gates

- [x] I001 Add unit tests for config loading.
- [x] I002 Add unit tests for data validators.
- [x] I003 Add unit tests for registry metadata helpers.
- [x] I004 Add unit tests for policy gate logic.
- [x] I005 Add API tests for VTON request validation.
- [x] I006 Add API tests for LLM request validation.
- [x] I007 Add integration test for data pipeline.
- [x] I008 Add integration test for model registration.
- [x] I009 Add integration test for promotion rejection.
- [x] I010 Add integration test for promotion approval.
- [x] I011 Add smoke test for full local stack startup. (`make app-smoke` uses a native Go checker to start Compose in the disposable `tryops_app_smoke` project with fresh volumes, verify 18/18 checks across Console, SPA fallback, gateway->API health/readiness, LLM generation, evaluation-summary API, edge-auth rejection, VTON artifacts, gateway metrics, guardrail, Prometheus, Grafana, MinIO, and MLflow, then tear the project down; report: `artifacts/eval/full_stack/full_stack_smoke.json`.)
- [x] I012 Add benchmark test for VTON inference latency.
- [x] I013 Add benchmark test for LLM latency and tokens/sec.
- [x] I014 Add regression test for VTON output metadata.
- [x] I015 Add regression test for LLM output format.
- [x] I016 Add quality gate for VTON minimum score or maximum regression.
- [x] I017 Add quality gate for LLM minimum score or maximum regression.
- [x] I018 Add cost gate for excessive latency or memory.
- [x] I019 Add security gate for unsafe dependency or missing scan.
- [x] I020 Add final acceptance test that exercises the professor demo path. (`make professor-demo-acceptance` builds `native/go/tryops-demo-acceptance`, runs the bad-candidate gate live, validates Pareto, energy, full-stack, VTON, lineage, promotion, rollback, and governance evidence, and emits `artifacts/eval/demo_acceptance/professor_demo_acceptance.json`.)

### J. Security, Responsible AI, and Governance

- [x] J001 Create AI risk register version 1.
- [x] J002 Map major risks to NIST AI RMF concepts.
- [x] J003 Map LLM risks to OWASP Top 10 for LLM Applications.
- [x] J004 Add prompt injection test cases for the LLM service.
- [x] J005 Add sensitive information disclosure tests for the LLM service.
- [x] J006 Add denial-of-service tests based on oversized prompts.
- [x] J007 Add image payload abuse tests based on oversized or malformed files.
- [x] J008 Add dependency lockfile.
- [x] J009 Generate SBOM if tooling is available.
- [x] J010 Run vulnerability scanning if tooling is available. (`make vulnerability-scan-sample` builds `native/go/tryops-vuln-scan`, runs available `npm audit` for `web/` with 0 vulnerabilities, and emits `tryops.vulnerability_scan.v1`; `make native-live-supply-chain-sample` now executes pinned Syft/Trivy/Cosign containers and emits `tryops.live_supply_chain.v1` with 613 Syft packages, 0 HIGH/CRITICAL Trivy findings, and verified Cosign SBOM signature evidence.)
- [x] J011 Pin model sources and record licenses.
- [x] J012 Record dataset licenses and usage restrictions.
- [x] J013 Add model card template.
- [x] J014 Add data card template.
- [x] J015 Add approval checklist before model promotion.
- [x] J016 Add audit log for promotion decisions.
- [x] J017 Add least-privilege API key simulation for admin actions.
- [x] J018 Add privacy note for user-uploaded images.
- [x] J019 Add bias and representation limitations section for VTON datasets.
- [x] J020 Add responsible AI limitations and residual risk section to the final report.

### K. Product Experience, Dashboard, and Demo

**Design intent.** Module K is the single React/Vite **"mission control"** surface that turns the whole platform into a 3-minute story for a professor and a 30-minute deep dive for an examiner — the realization of the [Control Room UI](#control-room-ui-product-polish) design. Two product rules keep it honest and low-risk: **(1) every panel reads an artifact or API that already exists** (Pareto/energy/SLO JSON, governance report, lineage, `/v1` metrics, Grafana), so the UI adds no new backend and cannot drift from the evidence; **(2) the UI degrades, never fails** — a degraded-mode banner serves seeded, lineage-backed outputs when the GPU or network is unavailable. Build order: live shell and interactive inference first, read-only evidence views second, the incident/rollback console last. Stack: React/Vite static app served by the Rust gateway, typed API client over the existing FastAPI/Rust `/api` contract, and native edge controls for proxy/static/quota/guardrails.

Items list the **data source that powers them** so each is a thin view, not new logic.

- [~] K001 VTON Studio: person+garment upload and output. (`web/src/components/VtonStudio.tsx` runs `/api/vton/infer` with seeded asset paths and image previews; browser upload/object serving remains.)
- [x] K002 Side-by-side baseline vs candidate VTON outputs. (`/api/vton/comparison` serves `tryops.vton_comparison.v1` with artifact URLs; `/api/artifacts/file` safely serves PNG/JSON evidence; `web/src/components/VtonStudio.tsx` renders person, garment, and two output images with metrics/failure labels; `make app-smoke` proves comparison JSON and PNG bytes through the Rust gateway.)
- [~] K003 Model version + latency badge next to each output. (LLM response metrics render live; VTON output image badge remains.)
- [~] K004 Feedback buttons for VTON output quality. (LLM feedback is wired to `POST /api/feedback`; VTON-specific feedback placement remains.)
- [x] K005 LLM Playground: prompt and response. (`web/src/components/LlmPlayground.tsx` posts to `/api/llm/generate`.)
- [x] K006 LLM variant selector (baseline / champion / challenger / candidate). (Source: safe aliases and API routing contract.)
- [~] K007 Latency / VRAM / tokens-sec / **energy** badges next to each LLM response. (Latency, memory, tokens/sec, quota, trace, and cost render; true VRAM/energy exporters remain.)
- [x] K008 Model registry viewer (candidate/challenger/champion/archived/rejected). (`web/src/components/RegistryView.tsx`.)
- [x] K009 Pipeline run history page. (`native/go/tryops-evaluation-index` now aggregates `run_context.json`, `openlineage_run_event.json`, and `lineage.json` into `pipeline_runs`; `/api/evaluations/summary` serves the run ledger; `web/src/components/PipelineRunsView.tsx` renders the Runs page; `make app-smoke` proves `pipeline_runs`, `run-vton-001`, and `COMPLETE` through the Rust gateway.)
- [x] K010 Evaluation report viewer (benchmark / Pareto / energy / drift). (`native/go/tryops-evaluation-index` generates `tryops.evaluation_index.v1`; `/api/evaluations/summary` serves it; `web/src/components/EvaluationView.tsx` renders highlights and a report registry; `make app-smoke` proves the endpoint through the Rust gateway.)
- [~] K011 Embedded monitoring panels. (Live dashboard tiles and recent request table exist; embedded Grafana panels remain.)
- [~] K012 Governance approval + risk-control status page. (Lineage lookup and signed-artifact list exist; full governance report view remains.)
- [~] K013 Incident-simulation console (trigger the bad-deploy drill). (Incident posture rows, the live bad-candidate gate action, the rollback drill action, and the native incident workflow/postmortem evidence panel exist; live Alertmanager-trigger controls remain.)
- [x] K014 Rollback demonstration button. (`web/src/components/IncidentView.tsx` runs a rollback drill by loading `artifacts/deployments/rollback_state.json`; `src/tryops/artifacts.py` and `native/rust/tryops-gateway/src/proxy.rs` allow deployment JSON artifacts with traversal/extension preflight; `native/go/tryops-stack-smoke/scenarios.go` proves `rollback_state_artifact_through_gateway` in `make app-smoke`.)
- [x] K015 Create seeded demo examples that always work.
- [x] K016 Create degraded-mode examples for weak hardware.
- [x] K017 3-minute professor demo script. (`docs/presentation_outline.md` → 3-minute path: smoke → block-a-bad-model → Pareto → energy.)
- [x] K018 10-minute deep technical demo script. (`docs/presentation_outline.md` → 10-minute path.)
- [x] K019 30-minute defense walkthrough. (`docs/presentation_outline.md` → 30-minute path + `docs/defense_qa.md`.)
- [x] K020 Record a backup video demo. (`make professor-demo-video` uses the native Go recorder in `native/go/tryops-demo-recorder/`, renders 9 seeded frames from `web/src/professor_demo_storyboard.json`, encodes `artifacts/demo/professor_demo_video/professor_demo_backup.mp4` with FFmpeg, and writes passing `tryops.professor_demo_video.v1` evidence to `artifacts/eval/demo_video/professor_demo_video.json`.)
- [x] K021 Control-room shell: one app with left-nav to Studio / Playground / Lineage / Releases / Governance / Incidents, plus a global degraded-mode banner. (`web/src/App.tsx`, `web/src/components/AppShell.tsx`, `web/src/components/StatusBanner.tsx`.)
- [~] K022 Lineage Viewer: click any output → dataset version, model version, pipeline run, metrics, git commit, container digest, signature, approval. (Manual request-ID lookup exists; richer click-through graph remains.)
- [~] K023 Champion/Challenger release board: current production vs candidate with per-gate pass/fail and the promotion decision. (Stage lanes exist; per-gate promotion artifact view remains.)
- [x] K024 Optimization Pareto panel: interactive quality-vs-latency-vs-VRAM-vs-**energy** frontier with the recommended variant highlighted. (`native/go/tryops-evaluation-index/optimization.go` emits `optimization_panel` from Pareto, leaderboard, and energy artifacts; `web/src/components/EvaluationView.tsx` renders an interactive quality-vs-latency frontier, variant detail, table, and recommended/frontier badges; `make app-smoke` requires `recommended_variant="4bit"` through the Rust gateway.)
- [x] K025 Sustainability panel: Wh-per-1k-tokens and gCO2e-per-1k-tokens per variant + the carbon-gate verdict. (The same `optimization_panel` carries per-variant Wh/1k tokens, SCI gCO2e/1k tokens, greenest variant, and carbon gate verdict; the Evaluation view renders these in metric tiles, variant detail, and the table; `make app-smoke` requires `carbon_gate_verdict="pass"`.)
- [x] K026 "Block a bad model" live widget: run the failing candidate through the gate on screen and show the rejection. (`web/src/components/IncidentView.tsx` posts the seeded bad VTON candidate through `/api/promotion/evaluate`; `web/src/api.ts` sends the signed-artifact preflight header; `native/go/tryops-stack-smoke/scenarios.go` proves `bad_candidate_gate_through_gateway` with `approved=false` through the Rust gateway in `make app-smoke`.)
- [x] K027 Professor demo mode: a guided, seeded, always-green walkthrough that needs no GPU or network. (`web/src/components/ProfessorDemoView.tsx` adds the Console view; `web/src/data.ts` seeds the seven-step path across stack preflight, quota, bad-model gate, LLM optimization, VTON quality, lineage, rollback, and governance; `make professor-demo-acceptance` now validates the native quota ledger plus the demo source contract and passes 12/12 checks.)
- [~] K028 Accessibility + screenshot/export pass so every panel is presentable in slides and the backup video. (Responsive CSS, labels, aria-hidden icons, keyboard-native controls, and generated professor-demo video frames exist; broader per-panel screenshot/export/accessibility evidence remains.)

**First slice (highest leverage, zero new backend):** ship K021 (shell) + K010 (evaluation report viewer) + K024 (Pareto panel) + K025 (sustainability panel) + K026 (block-a-bad-model widget) — five read-only views over artifacts that already exist, which alone tell the platform story end to end.

**Acceptance gate (Gate K):** a professor can, from the control room and with no terminal, (a) see a candidate blocked by the gate, (b) compare optimized LLM variants on quality/latency/VRAM/energy, (c) open any output's full lineage, and (d) trigger a rollback — with a degraded-mode banner proving it still works offline.

### L. Documentation, Reporting, and Project Management

- [x] L001 Create README with project thesis, setup, and demo commands.
- [x] L002 Create docs folder with architecture, data, models, pipelines, monitoring, and governance pages.
- [x] L003 Maintain weekly progress log.
- [x] L004 Maintain decision log.
- [x] L005 Maintain experiment log.
- [x] L006 Maintain risk register.
- [x] L007 Maintain known limitations page.
- [x] L008 Write final report outline by Month 2.
- [x] L009 Fill final report background and literature review. (`reports/final_report.md` §5.)
- [x] L010 Fill final report methodology. (`reports/final_report.md` §8–12, 15.)
- [x] L011 Fill final report implementation. (`reports/final_report.md` §6–14.)
- [x] L012 Fill final report evaluation. (`reports/final_report.md` §15–16, with real measured tables.)
- [~] L013 Add diagrams to the report. (Report carries metric tables and references the architecture diagrams in `docs/architecture.md`; rendered figures still to be authored.)
- [x] L014 Add metric tables to the report. (R1/R2/SLO/energy tables in `reports/final_report.md` §16.)
- [x] L015 Add failure case analysis to the report. (`reports/final_report.md` §17: rubric overfit, 8-bit regression, SLO non-transfer.)
- [x] L016 Add enterprise maturity assessment to the report.
- [x] L017 Add future work for scaling to real enterprise deployment. (`reports/final_report.md` §19; Wave 2 themes M–U.)
- [x] L018 Create final presentation slides. (`docs/presentation_outline.md`: 15-slide sequence + demo scripts.)
- [x] L019 Create defense Q&A with tough questions and concise answers. (`docs/defense_qa.md`.)
- [ ] L020 Freeze final release artifacts and tag the project state. (Repository is initialized and pushed; final release freeze/tag remains until the product-ready gate is complete.)

## Weekly Execution Rhythm

Every week should produce visible evidence:

- One artifact: code, doc, diagram, metric table, benchmark, dashboard, or demo improvement.
- One experiment: model, pipeline, evaluation, security test, or benchmark.
- One reflection: what changed, what failed, what evidence was learned, and what will be improved next.

Weekly loop:

1. Monday: choose the highest-value backlog items and define acceptance criteria.
2. Tuesday to Thursday: implement, test, and log results.
3. Friday: run reproducibility checks and update metrics.
4. Weekend: write the weekly report, update risk register, and prepare next week.

## Milestone Acceptance Gates

### Gate 1: Research Ready

- Literature table contains MLOps, VTON, LLM optimization, serving, monitoring, and governance.
- Research questions are explicit.
- Scope is realistic for available hardware.

### Gate 2: Platform Skeleton Ready

- Services start locally.
- MLflow records runs.
- Data validation produces a report.
- API health checks pass.

### Gate 3: First Model Lifecycle Ready

- A candidate model is evaluated.
- A registry entry is created.
- A policy gate makes a promotion decision.
- Serving uses model aliases.

### Gate 4: VTON Workload Ready

- VTON inference works on seeded examples.
- Evaluation report includes visual and numeric evidence.
- Failure gallery exists.
- Generated output lineage is traceable.

### Gate 5: LLM Optimization Ready

- Baseline and optimized LLM variants are benchmarked.
- Memory, latency, throughput, and quality are compared.
- Best variant is justified.
- Fallback routing works.

### Gate 6: Enterprise Controls Ready

- Observability dashboards exist.
- Risk register exists.
- Security checks exist.
- Promotion approval and rollback are demonstrated.

### Gate 7: Final Defense Ready

- Demo is reliable.
- Report is complete.
- Slides tell the story clearly.
- Reproducibility guide has been tested.
- Backup demo video exists.

## Risk Register Starter

| Risk | Impact | Mitigation |
| --- | --- | --- |
| VTON model too heavy for hardware | Demo fails or becomes slow | Use pretrained inference, small benchmark subset, async jobs, and degraded mode |
| Dataset licensing unclear | Cannot safely present results | Use public datasets with documented terms and cite every source |
| LLM quantization dependencies fail | Optimization scope weakens | Support multiple paths: bitsandbytes, GGUF, vLLM, or documented benchmark-only comparison |
| Too much time spent on UI | MLOps core suffers | Build functional UI only after pipeline and registry work |
| Metrics are too shallow | Professor sees a demo, not research | Define quality, latency, memory, cost, governance, and reliability metrics early |
| Monitoring is fake | Enterprise story weakens | Instrument real API and pipeline events, even if scale is small |
| Security controls are only written | Governance story weakens | Add at least prompt injection tests, payload validation, dependency scan, and approval logs |
| Final demo depends on internet | Defense risk | Prepare local seeded examples and backup video |

## Final Report Structure

1. Abstract.
2. Introduction and motivation.
3. Problem statement.
4. Research questions.
5. Related work: MLOps, VTON, LLM quantization, serving, monitoring, governance.
6. Enterprise architecture.
7. Data governance and datasets.
8. VTON methodology.
9. LLM optimization methodology.
10. MLOps pipeline design.
11. Model registry and governance.
12. Serving and deployment.
13. Observability and feedback loops.
14. Security and responsible AI.
15. Evaluation.
16. Results.
17. Failure analysis.
18. Limitations.
19. Future work.
20. Conclusion.

## Final Presentation Shape

Slide sequence:

1. Title: TryOps, Enterprise MLOps for VTON and Efficient LLM Serving.
2. The problem: ML demos are easy, production ML is hard.
3. The thesis: MLOps is the core product.
4. Workloads: VTON and LLM optimization.
5. Architecture diagram.
6. Data and artifact lifecycle.
7. Pipeline lifecycle.
8. Model registry and promotion gates.
9. VTON results.
10. LLM optimization results.
11. Observability dashboard.
12. Governance and risk controls.
13. Demo.
14. Evaluation summary.
15. Limitations and future work.

## Final Quality Bar

The project is excellent only if these statements are true:

- A new model cannot enter serving without evaluation evidence.
- A generated output can be traced back to data, code, config, model, and run metadata.
- The optimized LLM is compared against a baseline with reproducible measurements.
- The VTON model is evaluated with both visual and quantitative evidence.
- The platform records operational metrics during real requests.
- The final report discusses failures honestly.
- The demo works even if a network dependency fails.
- The work shows engineering maturity, not only model experimentation.

## Production Application Build Plan — "TryOps Console" (Enterprise End-User Product)

Canonical detailed plan: `docs/production_app_plan.md`. Research refresh: 2026-06-12.

Goal: turn the platform into a **real, runnable enterprise product** an end user actually uses — browser console, backend, database, services, monitoring, dashboard, quota, audit, incident flow — on top of the existing real LLM (R1/R2), real diffusion VTON, native Rust/Go/C++ boundary, and governance spine.

Current readiness: backend/data/native edge are real; the browser Console still needs screenshot/export/accessibility hardening, while production Kubernetes External Secrets sync, live OTLP exporters/full traces, and the production runbook are not done yet. The product must remain `make`-runnable locally with deterministic degraded-mode fallbacks when GPU/network dependencies are unavailable.

### Research-backed direction
- **Frontend/static serving:** Vite production build -> `web/dist`; local serving through FastAPI `StaticFiles`; production static serving through nginx or Rust edge profile.
- **Native hot path:** Rust owns gateway/session/quota/rate/body/trace/static-edge and semantic-cache admission plus C++ lookup invocation paths; Go owns controller/guardrail/jobs/webhooks/load gates; C++ owns vector/cache lookup, image metrics, policy/eval/stat kernels; Python stays BFF/control-plane/model-adapter glue.
- **Enterprise profile:** Docker Compose healthchecks/readiness, `.env.example` plus Compose secret loading, native Go secret-rotation/workload-identity contract evidence, Kubernetes Vault `SecretStore`/`ExternalSecret` manifests, native dependency-lock evidence across Python/Node/Rust/Go, native Rust TLS termination with Compose certificate/key secrets, Prometheus/Grafana provisioning, OpenTelemetry Collector, native Postgres migration/pooling, backup/restore, MinIO object URLs, GitHub Actions CI, SBOM/vuln/signing gates with open-source tooling, and native CI contract evidence.
- **Cluster option:** keep local HF/diffusers fallback, then add optional KServe/vLLM serving after the local product slice is proven.

### Build phases (each real, tested, `make`-runnable)

- [x] **P1 — Data layer.** DONE: `src/tryops/db.py` (SQLite, Postgres-compatible SQL) — requests/feedback/jobs/models/audit_log + dashboard rollup, 4 tests, `make db-init`.
- [x] **P2 — Product backend.** FastAPI BFF exposes LLM, VTON, history, request detail, feedback, models, promotion, lineage, dashboard rollup, native quota, and online-experiment route/analysis routes; real paths keep deterministic fallbacks; requests/feedback/models persist to DB; admin/read and promotion scopes are enforced.
- [~] **P3 — Frontend.** PARTIAL: React/Vite/TypeScript Console shell, typed API client, LLM Playground with direct/canary/A-B/bandit routing, VTON Studio contract form with persisted side-by-side comparison outputs, Dashboard, Request History, Pipeline Runs, Model Registry, Evaluation evidence plus optimization/Pareto/sustainability panel, Experiments board, Governance, Incident posture plus live bad-candidate and rollback drills, native incident workflow/postmortem evidence loading, API-key session field, RBAC role-aware navigation, degraded banner, and responsive styling are implemented under `web/`; browser upload/download controls, full audit-log UI, live alert workflow controls, screenshots, and accessibility/export hardening remain.
- [x] **P4 — Services & edge wiring.** Rust gateway reverse-proxies `/api/*` to FastAPI `/v1/*`, adds request IDs, propagates trace context, enforces native rate/payload/signed-artifact/quota controls plus artifact-path preflight, calls the Go guardrail sidecar before LLM generation, and `docker-compose` ties gateway+api+Postgres+Prometheus+Grafana+guardrail+MinIO+MLflow with healthchecks/restart policies. `make app-smoke` now validates the stack through a disposable Compose project so stale local volumes do not taint readiness.
- [~] **P5 — Monitoring & dashboard.** API metrics, native Rust gateway metrics, native Go runtime telemetry, OpenTelemetry Collector wiring, native trace/log correlation evidence, and Alertmanager page/ticket routing are in place; remaining work: in-app timeseries, audit-log UI, external pager/chat credentials, and live OTLP exporters for full gateway->API->model trace stitching.
- [~] **P6 — Enterprise hardening.** PARTIAL: Rust edge API-key/JWT auth preflight, viewer/operator/admin RBAC session and nav enforcement, native edge limits, quota admission, optional file quota persistence, opt-in Postgres-backed distributed quota admission with fail-closed behavior, Postgres quota usage upsert mirroring, native Postgres migration/pooling evidence, native Postgres/MinIO backup-restore drill evidence, Valkey-compatible quota counter mirroring, `.env.example` plus Compose secret loading, native Go secret-rotation/workload-identity contract evidence, live Vault KV v2 secret retrieval/rotation evidence, Kubernetes Vault `SecretStore`/`ExternalSecret` manifests, native dependency-lock contract evidence across Python/Node/Rust/Go, native rustls TLS termination, payload limits, Rust->Go guardrail enforcement, native Go full-stack load/SLO evidence, native Go incident workflow/postmortem evidence, GitHub Actions plus native Go CI/supply-chain contract evidence, and local live Syft/Trivy/Cosign execution are in place. Remaining work: production Kubernetes External Secrets sync, external k6/locust confirmation, and external error-tracker DSN exercise.
- [~] **P7 — Demo & docs.** PARTIAL: `docs/presentation_outline.md` contains the professor demo path and `make professor-demo-acceptance` now verifies the live bad-candidate gate plus seeded Pareto, energy, full-stack, VTON, lineage, promotion, rollback, and governance artifacts. Remaining work: seed data loader, product runbook, screenshots/walkthrough, and full end-user/admin guide.
- [~] **P8 — Native-first product expansion.** PARTIAL: local P8 rows PA072-PA086 are closed by verified native evidence. Rust gateway now serves `web/dist` with SPA fallback, performs API-key/JWT auth preflight, terminates optional rustls HTTPS, makes native semantic-cache admission decisions and optional C++ vector-cache lookups before FastAPI for LLM generation, mirrors accepted quota usage into Postgres plus Valkey-compatible counters with hashed-tenant usage snapshots, can use Postgres row locks as the shared quota admission ledger when `TRYOPS_GATEWAY_QUOTA_POSTGRES_ADMISSION=true`, falls back to the local quota ledger when a non-admission durable mirror is unavailable, emits the shared native trace/log envelope as JSONL, and has a validated split-image contract with Rust builder/runtime ABI checks for gateway/controller/guardrail/benchmark/C++ tools/API/web assets; native Go modules now cover VTON/LLM job execution, signed audit/webhook event dispatch, full-stack gateway/BFF load generation with SLO reporting, native CI/supply-chain contract validation plus live Syft/Trivy/Cosign evidence, native dependency-lock contract validation, native secret-rotation/workload-identity contract validation plus live Vault KV rotation, native incident workflow/postmortem evidence, distributed quota admission validation, config-contract drift checks, TLS termination contract validation, native Postgres migration/pool execution, native Postgres/MinIO backup-restore drills, container-contract validation, quota read-model/showback generation for the BFF dashboard, trace-envelope validation/reporting, observability Collector/correlation validation, Alertmanager routing validation, runtime telemetry export, SLO regression gating over native benchmark output, and a CI-grade Rust/Go/C++ performance-budget report; native C++ VTON preprocessing, image-quality metrics, production A/B/bandit routing, semantic-cache lookup, and trace-envelope validation now flow through edge/API/evidence paths. Production Kubernetes External Secrets sync, external k6/locust confirmation, external error-tracker DSN exercise, and live OTLP exporters remain.

### Execution order
P3 Console shell -> thin LLM slice -> VTON product slice -> operator control room -> native enterprise boundary -> production profile. Ship the thin vertical slice first: UI -> Rust gateway -> API -> real/fallback LLM -> DB -> feedback -> dashboard -> Grafana.

### Acceptance (Gate: Product Ready)
A user opens the Console in a browser and can, with no terminal, run LLM and VTON requests, see metrics/quota/trace/lineage, submit feedback, review history/dashboard/registry/audit, and as an admin promote or block a model through policy-gated controls. The full stack starts with `make app-up` and is smoke-tested with `make app-smoke`; native edge/job/SLO/config/container/CI/load/trace/observability/alerts/postgres/backup/TLS/performance/quota-read-model/distributed-quota/runtime-telemetry/live-secret evidence comes from `make native-rust-smoke`, `make native-edge-cache-smoke`, `make native-edge-guardrail-smoke`, `make native-quota-ledger-smoke`, `make native-distributed-quota-smoke`, `make native-secret-rotation-live`, `make native-quota-read-model-sample`, `make native-runtime-telemetry-sample`, `make native-observability-contract-sample`, `make native-alertmanager-contract-sample`, `make native-db-migrator-sample`, `make native-backup-restore-sample`, `make native-tls-contract-sample`, `make native-tls-smoke`, `make native-static-smoke`, `make native-job-runner-sample`, `make vton-native-api-sample`, `make gateway-benchmark-native`, `make native-fullstack-load-sample`, `make native-ci-contract-live`, `make native-slo-gate-sample`, `make native-config-contract-sample`, `make native-container-contract-sample`, `make native-trace-envelope-sample`, and `make native-performance-budget-sample`; backend contracts remain covered by the Python test suite. The professor-demo evidence bundle is gated by `make professor-demo-acceptance`.
