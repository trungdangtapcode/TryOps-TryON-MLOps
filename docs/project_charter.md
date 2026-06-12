# TryOps Project Charter

## Thesis

TryOps is an enterprise MLOps platform for governed virtual try-on and optimized LLM serving.

## Motivation

Most ML projects shown in class stop at a notebook, a model, or a UI demo. TryOps is designed to show the harder production problem: how models become trusted, measured, deployed, monitored, rolled back, and improved.

## Users

- Professor or evaluator: needs a clear demo and strong engineering evidence.
- ML engineer: runs experiments, evaluations, and model promotion.
- Platform engineer: operates services, pipelines, artifacts, dashboards, and policy gates.
- Risk reviewer: checks model cards, data cards, vulnerabilities, approval logs, and residual risks.

## Scope

Included:

- MLOps control plane.
- VTON proof workload.
- LLM optimization proof workload.
- Open-source model lifecycle tooling.
- Rust, Go, and C++ native production-boundary scaffolds.
- Policy-gated promotion with model/data cards and lineage.

Excluded from the main path:

- Paid managed MLOps platforms.
- Training huge foundation models from scratch.
- Private or unlicensed person images.
- Unbounded shopping assistant features that distract from the MLOps thesis.

## Success Criteria

- A candidate model cannot become champion without evaluation evidence.
- Every generated output can be traced to model, data, code, run, metrics, and policy decision.
- VTON and LLM workloads have clear quality, latency, memory, and cost metrics.
- Python is not the claimed production boundary; Rust/Go/native modules carry that architecture story.
- The demo has a local fallback and reproducible commands.

