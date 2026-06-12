from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tryops.contracts import ModelCandidate, PromotionDecision


@dataclass(frozen=True)
class RegistryEntry:
    name: str
    version: str
    alias: str
    workload: str
    candidate_id: str
    metrics: dict[str, float]
    artifact_uris: dict[str, str]
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "alias": self.alias,
            "workload": self.workload,
            "candidate_id": self.candidate_id,
            "metrics": dict(self.metrics),
            "artifact_uris": dict(self.artifact_uris),
            "tags": dict(self.tags),
        }


def build_registry_entry(
    candidate: ModelCandidate,
    decision: PromotionDecision,
    *,
    alias: str,
) -> RegistryEntry:
    if alias == "champion" and not decision.approved:
        raise ValueError("cannot assign champion alias to a rejected candidate")
    if alias not in {"candidate", "challenger", "champion", "rejected", "archived"}:
        raise ValueError(f"unsupported registry alias '{alias}'")

    return RegistryEntry(
        name=candidate.model_name,
        version=candidate.model_version,
        alias=alias,
        workload=candidate.workload,
        candidate_id=candidate.candidate_id,
        metrics=dict(candidate.metrics),
        artifact_uris=dict(candidate.artifacts),
        tags={
            "risk_status": candidate.risk_status,
            "signed": str(candidate.signed).lower(),
            "target_stage": decision.target_stage,
            "decision": "approved" if decision.approved else "rejected",
            "dataset_version": str(candidate.metadata.get("dataset_version", "")),
            "pipeline_run_id": str(candidate.metadata.get("pipeline_run_id", "")),
        },
    )

