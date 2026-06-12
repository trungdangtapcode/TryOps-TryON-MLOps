# ADR 0002: Policy-Gated Model Promotion

## Status

Accepted.

## Decision

Model candidates cannot become champion unless they pass policy gates for artifacts, approvals, risk
status, vulnerability status, signature/provenance status, SafeTensors-only model scanning, and
workload-specific metrics.

## Rationale

This makes MLOps the center of the project. The model is not trusted because it exists; it is trusted because evidence was produced and checked.
