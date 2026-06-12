# Enterprise MLOps Maturity Assessment

## Current State

TryOps is between maturity level 1 and 2:

- Code structure exists.
- Reproducible local smoke command exists.
- Data validation exists.
- Policy-gated promotion exists.
- Generated model/data cards and lineage exist.
- Native production boundary is scaffolded.

## Missing for Higher Maturity

- Real training and inference pipelines.
- Live MLflow tracking writes.
- Live monitoring dashboards from real requests.
- Scheduled retraining or drift-triggered re-evaluation.
- Kubernetes deployment with KServe.
- SBOM/signing/scanning automation.
- Real benchmark and human evaluation results.

## Target

Reach a local equivalent of maturity level 3-4 by the final demo:

- Automated evaluation before promotion.
- Registry-backed champion/challenger aliases.
- Observability from real requests.
- Reproducible model/data lineage.
- Rollback and incident drill.
- Governance evidence for every promoted model.

