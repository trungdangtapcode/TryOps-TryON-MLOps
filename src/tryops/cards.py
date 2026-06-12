from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tryops.contracts import ModelCandidate, PromotionDecision


def render_model_card(candidate: ModelCandidate, decision: PromotionDecision) -> str:
    """Render a lightweight model card from tracked candidate evidence."""

    metric_lines = "\n".join(
        f"- {name}: {value}" for name, value in sorted(candidate.metrics.items())
    )
    artifact_lines = "\n".join(
        f"- {name}: {uri}" for name, uri in sorted(candidate.artifacts.items())
    )
    approval_lines = "\n".join(f"- {approval}" for approval in candidate.approvals) or "- None"
    reason_lines = "\n".join(f"- {reason}" for reason in decision.reasons)
    warning_lines = "\n".join(f"- {warning}" for warning in decision.warnings) or "- None"
    provenance = candidate.metadata.get("model_provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}

    return f"""# Model Card: {candidate.model_name}

Generated: {datetime.now(UTC).isoformat()}

## Identity

- Candidate ID: {candidate.candidate_id}
- Workload: {candidate.workload}
- Version: {candidate.model_version}
- Risk Status: {candidate.risk_status}
- Signed: {candidate.signed}

## Metrics

{metric_lines}

## Artifacts

{artifact_lines}

## Provenance

- Provenance Artifact: {candidate.artifacts.get("model_provenance", "missing")}
- Status: {provenance.get("status", "missing")}
- Statement Type: {provenance.get("statement_type", "missing")}
- Predicate Type: {provenance.get("predicate_type", "missing")}
- Signature Mode: {provenance.get("signature_mode", "missing")}
- Signer Identity: {provenance.get("signer_identity", "missing")}
- Verified: {provenance.get("verified", False)}

## Approvals

{approval_lines}

## Promotion Decision

- Target Stage: {decision.target_stage}
- Approved: {decision.approved}

Reasons:

{reason_lines}

Warnings:

{warning_lines}

## Intended Use

This candidate is part of the TryOps enterprise MLOps demonstration. It must only be
served through the model alias and promotion workflow, not by direct file path.

## Limitations

This card is generated from pipeline evidence. Human review must still inspect
dataset suitability, visual failure cases, safety risks, and operational readiness.
"""


def render_data_card(manifest: dict[str, Any], validation_report: dict[str, Any]) -> str:
    """Render a data card from a dataset manifest and validation output."""

    dataset_id = manifest.get("dataset_id", "unknown")
    license_name = manifest.get("license", "mixed or unspecified")
    source = manifest.get("source", "unspecified")
    stats = validation_report.get("stats", {})
    split_counts = stats.get("split_counts", {})
    split_lines = "\n".join(f"- {name}: {count}" for name, count in sorted(split_counts.items()))
    error_lines = "\n".join(f"- {error}" for error in validation_report.get("errors", [])) or "- None"

    return f"""# Data Card: {dataset_id}

Generated: {datetime.now(UTC).isoformat()}

## Source

- Source: {source}
- License: {license_name}

## Validation

- Passed: {validation_report.get("passed")}
- Entry Count: {stats.get("entry_count", 0)}
- Unique IDs: {stats.get("unique_ids", 0)}
- Unique Checksums: {stats.get("unique_checksums", 0)}

## Splits

{split_lines or "- None"}

## Validation Errors

{error_lines}

## Privacy Notes

Do not commit private person images. Use public, licensed, or synthetic examples
for professor demos unless explicit consent and retention rules are documented.
"""
