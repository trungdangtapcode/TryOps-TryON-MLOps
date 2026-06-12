# ADR 0001: Open-Source Local-First Enterprise Architecture

## Status

Accepted.

## Decision

TryOps will use an open-source local-first stack with an enterprise Kubernetes profile.

## Rationale

The project must be impressive without depending on paid managed services. Local-first development keeps progress reliable, while the enterprise profile proves production architecture.

## Chosen Components

- Docker Compose for local development.
- Kubeflow Pipelines for enterprise pipeline orchestration.
- MLflow for tracking and registry.
- DVC and MinIO for data and artifact management.
- FastAPI and KServe for serving.
- vLLM for optimized LLM inference.
- Prometheus, Grafana, OpenTelemetry, and Evidently for observability.
- OPA, Trivy, Syft, and Cosign for governance and supply chain.

