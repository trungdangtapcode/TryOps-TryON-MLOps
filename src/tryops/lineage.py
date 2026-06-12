from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from tryops.contracts import ModelCandidate

OPENLINEAGE_PRODUCER = "https://github.com/tryops/tryops-local"
OPENLINEAGE_SCHEMA_URL = "https://openlineage.io/spec/1-0-5/OpenLineage.json#/definitions/RunEvent"
OPENLINEAGE_BASE_FACET_SCHEMA_URL = (
    "https://raw.githubusercontent.com/OpenLineage/OpenLineage/main/spec/OpenLineage.json"
    "#/definitions/BaseFacet"
)


def build_lineage_record(
    candidate: ModelCandidate,
    *,
    request_id: str,
    output_uri: str,
) -> dict[str, Any]:
    """Build an auditable lineage record for a served model output."""

    metadata = candidate.metadata
    return {
        "schema_version": "tryops.lineage.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "output_uri": output_uri,
        "candidate_id": candidate.candidate_id,
        "workload": candidate.workload,
        "model": {
            "name": candidate.model_name,
            "version": candidate.model_version,
            "signed": candidate.signed,
        },
        "lineage": {
            "code_version": metadata.get("code_version"),
            "dataset_version": metadata.get("dataset_version"),
            "pipeline_run_id": metadata.get("pipeline_run_id"),
            "container_digest": metadata.get("container_digest"),
        },
        "artifacts": dict(candidate.artifacts),
        "provenance": {
            "model_provenance": candidate.artifacts.get("model_provenance"),
            "signed": candidate.signed,
            "status": _metadata_value(metadata, "model_provenance", "status"),
            "statement_type": _metadata_value(metadata, "model_provenance", "statement_type"),
            "predicate_type": _metadata_value(metadata, "model_provenance", "predicate_type"),
            "signature_mode": _metadata_value(metadata, "model_provenance", "signature_mode"),
            "signer_identity": _metadata_value(metadata, "model_provenance", "signer_identity"),
            "verified": _metadata_value(metadata, "model_provenance", "verified"),
        },
        "metrics": dict(candidate.metrics),
        "risk_status": candidate.risk_status,
    }


def build_openlineage_run_event(
    candidate: ModelCandidate,
    *,
    run_context: dict[str, Any],
    lineage_record: dict[str, Any],
    event_type: str = "COMPLETE",
) -> dict[str, Any]:
    """Build an OpenLineage RunEvent alongside the internal TryOps lineage JSON."""

    normalized_event_type = event_type.upper()
    if normalized_event_type not in {"START", "RUNNING", "COMPLETE", "ABORT", "FAIL", "OTHER"}:
        raise ValueError(f"unsupported OpenLineage eventType: {event_type}")

    run_id = _openlineage_run_id(
        candidate_id=candidate.candidate_id,
        tryops_run_id=str(run_context.get("run_id") or candidate.metadata.get("pipeline_run_id") or ""),
    )
    created_at = str(run_context.get("created_at") or lineage_record.get("created_at") or datetime.now(UTC).isoformat())
    event_time = created_at.replace("+00:00", "Z")
    dataset_version = str(candidate.metadata.get("dataset_version") or "unknown-dataset")
    code_version = str(candidate.metadata.get("code_version") or run_context.get("code", {}).get("version", "unknown"))

    return {
        "eventType": normalized_event_type,
        "eventTime": event_time,
        "run": {
            "runId": run_id,
            "facets": {
                "tryopsRun": _base_facet(
                    {
                        "candidateId": candidate.candidate_id,
                        "traceId": str(run_context.get("trace_id") or lineage_record.get("request_id") or ""),
                        "tryopsRunId": str(run_context.get("run_id") or ""),
                        "riskStatus": candidate.risk_status,
                        "signed": bool(candidate.signed),
                    }
                )
            },
        },
        "job": {
            "namespace": "tryops.local",
            "name": f"{candidate.workload}.local-promotion-pipeline",
            "facets": {
                "tryopsJob": _base_facet(
                    {
                        "workload": candidate.workload,
                        "modelName": candidate.model_name,
                        "modelVersion": candidate.model_version,
                        "codeVersion": code_version,
                    }
                )
            },
        },
        "inputs": [
            {
                "namespace": "tryops.dataset",
                "name": dataset_version,
                "facets": {
                    "tryopsDataset": _base_facet(
                        {
                            "datasetVersion": dataset_version,
                            "source": "promotion-candidate-metadata",
                        }
                    )
                },
            },
            {
                "namespace": "tryops.model",
                "name": f"{candidate.model_name}:{candidate.model_version}",
                "facets": {
                    "tryopsModel": _base_facet(
                        {
                            "candidateId": candidate.candidate_id,
                            "modelProvenance": candidate.artifacts.get("model_provenance", ""),
                            "provenanceVerified": bool(_metadata_value(candidate.metadata, "model_provenance", "verified")),
                        }
                    )
                },
            },
        ],
        "outputs": [
            {
                "namespace": "tryops.artifact",
                "name": str(lineage_record.get("output_uri") or ""),
                "facets": {
                    "tryopsArtifact": _base_facet(
                        {
                            "artifactType": "promotion_decision",
                            "candidateId": candidate.candidate_id,
                        }
                    )
                },
            }
        ],
        "producer": OPENLINEAGE_PRODUCER,
        "schemaURL": OPENLINEAGE_SCHEMA_URL,
    }


def _metadata_value(metadata: dict[str, Any], section: str, key: str) -> Any:
    value = metadata.get(section, {})
    if isinstance(value, dict):
        return value.get(key)
    return None


def _openlineage_run_id(*, candidate_id: str, tryops_run_id: str) -> str:
    material = f"tryops:{candidate_id}:{tryops_run_id}"
    return str(uuid5(NAMESPACE_URL, material))


def _base_facet(payload: dict[str, Any]) -> dict[str, Any]:
    facet = {
        "_producer": OPENLINEAGE_PRODUCER,
        "_schemaURL": OPENLINEAGE_BASE_FACET_SCHEMA_URL,
    }
    facet.update(payload)
    return facet
