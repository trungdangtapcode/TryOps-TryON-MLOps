from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelCandidate:
    """Promotion candidate produced by a training, evaluation, or optimization run."""

    candidate_id: str
    workload: str
    model_name: str
    model_version: str
    metrics: dict[str, float]
    artifacts: dict[str, str]
    approvals: list[str] = field(default_factory=list)
    risk_status: str = "unknown"
    vulnerabilities: dict[str, int] = field(default_factory=dict)
    signed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ModelCandidate":
        required = ["candidate_id", "workload", "model_name", "model_version", "metrics", "artifacts"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"candidate is missing required fields: {', '.join(missing)}")

        return cls(
            candidate_id=str(payload["candidate_id"]),
            workload=str(payload["workload"]),
            model_name=str(payload["model_name"]),
            model_version=str(payload["model_version"]),
            metrics={str(k): float(v) for k, v in dict(payload["metrics"]).items()},
            artifacts={str(k): str(v) for k, v in dict(payload["artifacts"]).items()},
            approvals=[str(item) for item in payload.get("approvals", [])],
            risk_status=str(payload.get("risk_status", "unknown")),
            vulnerabilities={
                str(k): int(v) for k, v in dict(payload.get("vulnerabilities", {})).items()
            },
            signed=bool(payload.get("signed", False)),
            metadata=dict(payload.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "workload": self.workload,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "metrics": dict(self.metrics),
            "artifacts": dict(self.artifacts),
            "approvals": list(self.approvals),
            "risk_status": self.risk_status,
            "vulnerabilities": dict(self.vulnerabilities),
            "signed": self.signed,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    target_stage: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "target_stage": self.target_stage,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
        }

