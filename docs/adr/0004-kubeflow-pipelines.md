# ADR 0004: Kubeflow Pipelines as Target Orchestrator

## Status

Accepted.

## Decision

Kubeflow Pipelines is the target enterprise workflow orchestrator for TryOps.

## Rationale

The project needs a visible, enterprise-grade ML DAG that can show data validation, evaluation, model registration, promotion policy, and artifact lineage. Kubeflow Pipelines matches the Kubernetes-oriented target architecture while still allowing local Python components to be developed first.

## Consequences

- Pipeline components must be written as container-friendly modules.
- Local scripts remain the development path until Kubernetes is available.
- Final enterprise deployment should translate the local promotion pipeline into Kubeflow components.
- The local skeleton now emits validated DAG evidence and a Kubeflow-style manifest before the live Kubeflow backend is installed.
