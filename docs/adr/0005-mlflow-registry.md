# ADR 0005: MLflow Tracking and Registry

## Status

Accepted.

## Decision

TryOps uses MLflow Tracking and MLflow Model Registry for experiment metadata, model versions, lifecycle aliases, metrics, and artifact references.

## Rationale

MLflow is lightweight enough for a student project but still maps to enterprise lifecycle concepts: experiment tracking, model registry entries, aliases, tags, artifacts, and lineage. It is easier to demonstrate and explain than a heavier platform dependency.

## Consequences

- Every candidate should have registry metadata.
- Aliases are limited to `candidate`, `challenger`, `champion`, `rejected`, and `archived`.
- Generated promotion evidence must include a registry entry artifact until live MLflow integration is wired.

