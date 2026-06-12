# ADR 0003: Native Production Boundary

## Status

Accepted.

## Decision

TryOps will not present Python as the production boundary. The production-facing architecture is:

- Rust gateway for external API traffic, request validation, timeouts, tracing, and preflight policy.
- Go controller for Kubernetes/platform reconciliation.
- Optimized inference runtimes for models: vLLM, KServe, Triton, and ONNX Runtime where appropriate.
- Python for ML research, training, evaluation, Kubeflow components, and experiment automation.

## Rationale

Python is excellent for ML iteration, but it is weaker as the primary production boundary for high-concurrency systems. A native boundary improves the enterprise story:

- Rust gives memory safety, predictable performance, and strong async networking.
- Go aligns with Kubernetes, controllers, cloud-native tooling, and operational services.
- C++ remains useful for custom inference kernels, Triton backends, ONNX Runtime integration, or image preprocessing.

## Current Workspace Constraint

This workspace currently has `g++`, Go, `cargo`, and `rustc` available in the active shell.
Therefore:

- The C++ native modules are compiled and tested locally.
- The Go controller and Go guardrail sidecar build and smoke locally.
- The modular Rust gateway builds, tests, and smokes locally as the compiled edge boundary.

## Final Target

The final platform should show this flow:

```text
React UI
  -> Rust Gateway
  -> Go platform/controller reconciliation where Kubernetes state is involved
  -> KServe / vLLM / Triton inference services
  -> MLflow registry / MinIO artifacts / Prometheus metrics
```
