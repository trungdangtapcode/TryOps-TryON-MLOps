from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tryops.contracts import ModelCandidate, PromotionDecision


DEFAULT_NATIVE_POLICY_CLI = Path("artifacts/native/tryops_policy_cli")


def serialize_candidate_for_native(candidate: ModelCandidate, *, target_stage: str) -> str:
    lines = [
        f"target_stage={target_stage}",
        f"candidate_id={candidate.candidate_id}",
        f"workload={candidate.workload}",
        f"model_name={candidate.model_name}",
        f"model_version={candidate.model_version}",
        f"risk_status={candidate.risk_status}",
        f"signed={'true' if candidate.signed else 'false'}",
        f"critical_vulnerabilities={int(candidate.vulnerabilities.get('critical', 0))}",
        f"high_vulnerabilities={int(candidate.vulnerabilities.get('high', 0))}",
    ]
    for name, value in sorted(candidate.metrics.items()):
        lines.append(f"metric.{name}={float(value)}")
    for name, value in sorted(candidate.artifacts.items()):
        lines.append(f"artifact.{name}={value}")
    for name, value in _flatten_metadata(candidate.metadata).items():
        lines.append(f"metadata.{name}={value}")
    for approval in candidate.approvals:
        lines.append(f"approval={approval}")
    return "\n".join(lines) + "\n"


def _flatten_metadata(metadata: dict[str, Any], *, prefix: str = "") -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, value in sorted(metadata.items()):
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_metadata(value, prefix=full_key))
        elif isinstance(value, list):
            flattened[full_key] = ",".join(str(item) for item in value)
        else:
            flattened[full_key] = str(value).lower() if isinstance(value, bool) else str(value)
    return flattened


def evaluate_with_native_policy(
    candidate: ModelCandidate,
    *,
    target_stage: str,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_POLICY_CLI", DEFAULT_NATIVE_POLICY_CLI))
    if not path.exists():
        return {
            "available": False,
            "cli_path": str(path),
            "reason": "native policy CLI not found",
        }
    wire_payload = serialize_candidate_for_native(candidate, target_stage=target_stage)
    completed = subprocess.run(
        [str(path)],
        input=wire_payload,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    if completed.returncode not in {0, 2}:
        return {
            "available": True,
            "cli_path": str(path),
            "error": completed.stderr.strip() or completed.stdout.strip(),
            "returncode": completed.returncode,
        }
    decision = json.loads(completed.stdout)
    return {
        "available": True,
        "cli_path": str(path),
        "returncode": completed.returncode,
        "wire_format": "tryops.native_policy.v1",
        "decision": decision,
    }


def native_decision_matches_python(
    native_result: dict[str, Any],
    python_decision: PromotionDecision,
) -> bool:
    if not native_result.get("available") or "decision" not in native_result:
        return False
    native_decision = native_result["decision"]
    return (
        bool(native_decision["approved"]) == python_decision.approved
        and str(native_decision["target_stage"]) == python_decision.target_stage
        and list(native_decision["reasons"]) == python_decision.reasons
    )
