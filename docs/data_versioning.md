# Data Versioning

## Decision

TryOps uses DVC for dataset and artifact versioning, backed by MinIO as a local S3-compatible remote.

## Current State

- `dvc.yaml` defines a first reproducible evidence-producing stage.
- `.dvc/config` points to the local MinIO remote `s3://tryops-artifacts/dvc`.
- `dvc.lock` pins the `validate_demo_manifest` stage dependencies and generated promotion evidence
  output hash.
- `make dvc-minio-sample` runs `dvc repro`, `dvc push`, and the native Go verifier
  `tryops_data_versioning`.
- The latest proof is `artifacts/eval/data_versioning/dvc_minio_report.json`
  (`tryops.dvc_minio_versioning.v1`) with 12 local DVC cache objects and 12 matching MinIO objects.

## Intended Commands

```bash
make app-up
make dvc-minio-sample
```

## Remote

```text
url = s3://tryops-artifacts/dvc
endpointurl = http://127.0.0.1:19000
```

The DVC CLI is installed locally under `artifacts/tools/dvc-venv` for this workspace. The remote
uses the Compose MinIO host port from `make app-up`.

## Rule

Large datasets and generated model artifacts should not be committed directly. They should be tracked by DVC and stored in MinIO or another documented artifact remote.
