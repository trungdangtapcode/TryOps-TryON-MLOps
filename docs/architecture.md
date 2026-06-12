# TryOps Architecture

## Thesis

TryOps is an enterprise MLOps control plane. VTON and optimized LLM serving are the two proof workloads.

## Local Profile

- FastAPI exposes development control-plane endpoints.
- A C++ policy engine verifies the promotion gate can move out of Python.
- Rust and Go services define the compiled production boundary: the Rust gateway fronts `/api/*`, and Go handles controller/guardrail services.
- MLflow tracks experiments and registry state.
- MinIO stores artifacts.
- DVC versions datasets and benchmark sets.
- Prometheus scrapes service metrics.
- Grafana shows operational dashboards.
- Python policy checks block unsafe promotion locally.

## Enterprise Profile

- Rust Axum gateway handles external API traffic, `/api/*` to `/v1/*` reverse proxying, request IDs, request validation, native rate/body limits, tracing, timeouts, quota admission, and signed-artifact preflight policy.
- Go platform controller reconciles model candidates, promotion decisions, and deployment aliases.
- Kubeflow Pipelines runs data validation, evaluation, quantization, registration, and promotion workflows.
- The local orchestration skeleton emits a Kubeflow-target DAG manifest for validation, evaluation, supply-chain evidence, governance mapping, promotion, and deployment packaging.
- KServe hosts VTON and vLLM inference services.
- OPA/Rego evaluates promotion policy.
- Trivy, Syft, and Cosign generate security evidence.
- OpenTelemetry connects traces, logs, metrics, model versions, and request IDs.

## Promotion Lifecycle

1. Candidate model is produced by a pipeline.
2. Evaluation report is generated.
3. Required artifacts are attached: model card, data card, evaluation report, and SBOM.
4. Security scan and signature status are recorded.
5. Policy gate evaluates metrics, risk, approvals, artifacts, and vulnerabilities.
6. Passing candidates can become challenger or champion.
7. Failing candidates are marked rejected with reasons.

## Wow Path

The most important final UI is a model lineage viewer. A professor should click a generated VTON image and see the model version, dataset version, code version, pipeline run, metrics, policy decision, and artifacts behind it.
