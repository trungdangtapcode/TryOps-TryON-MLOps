from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tryops.cards import render_data_card, render_model_card
from tryops.contracts import ModelCandidate
from tryops.lineage import build_lineage_record, build_openlineage_run_event
from tryops.native_openlineage import validate_openlineage_event
from tryops.native_policy import evaluate_with_native_policy, native_decision_matches_python
from tryops.pipelines.data_validation import validate_dataset_manifest
from tryops.policy import evaluate_promotion
from tryops.registry import build_registry_entry
from tryops.run_context import build_run_context


def run_local_promotion_pipeline(
    *,
    candidate_payload: dict[str, Any],
    dataset_manifest: dict[str, Any],
    target_stage: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Run the first local evidence-producing promotion workflow."""

    candidate = ModelCandidate.from_dict(candidate_payload)
    validation_report = validate_dataset_manifest(dataset_manifest)
    decision = evaluate_promotion(candidate, target_stage=target_stage)
    native_policy = evaluate_with_native_policy(candidate, target_stage=target_stage)
    if native_policy.get("available") and "decision" in native_policy:
        native_policy["matches_python"] = native_decision_matches_python(native_policy, decision)
    run_dir = output_dir / candidate.candidate_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_context = build_run_context(
        run_name="local-promotion-pipeline",
        run_id=str(candidate.metadata.get("pipeline_run_id", "")) or None,
        trace_id=f"trace-promotion-{candidate.candidate_id}",
    )

    lineage = build_lineage_record(
        candidate,
        request_id=run_context["trace_id"],
        output_uri=f"file://{run_dir / 'promotion_decision.json'}",
    )
    openlineage_event = build_openlineage_run_event(
        candidate,
        run_context=run_context,
        lineage_record=lineage,
        event_type="COMPLETE" if decision.approved and validation_report["passed"] else "FAIL",
    )
    registry_alias = target_stage if decision.approved else "rejected"
    registry_entry = build_registry_entry(candidate, decision, alias=registry_alias)

    artifacts = {
        "policy_candidate": candidate.to_dict(),
        "promotion_decision": decision.to_dict(),
        "data_validation": validation_report,
        "lineage": lineage,
        "openlineage_run_event": openlineage_event,
        "native_policy_decision": native_policy,
        "run_context": run_context,
        "registry_entry": registry_entry.to_dict(),
        "model_card": render_model_card(candidate, decision),
        "data_card": render_data_card(dataset_manifest, validation_report),
    }

    _write_json(run_dir / "promotion_decision.json", artifacts["promotion_decision"])
    _write_json(run_dir / "policy_candidate.json", artifacts["policy_candidate"])
    _write_json(run_dir / "data_validation.json", artifacts["data_validation"])
    _write_json(run_dir / "lineage.json", artifacts["lineage"])
    _write_json(run_dir / "openlineage_run_event.json", artifacts["openlineage_run_event"])
    artifacts["openlineage_validation"] = validate_openlineage_event(run_dir / "openlineage_run_event.json")
    _write_json(run_dir / "openlineage_validation.json", artifacts["openlineage_validation"])
    _write_json(run_dir / "native_policy_decision.json", artifacts["native_policy_decision"])
    _write_json(run_dir / "run_context.json", artifacts["run_context"])
    _write_json(run_dir / "registry_entry.json", artifacts["registry_entry"])
    (run_dir / "model_card.md").write_text(artifacts["model_card"], encoding="utf-8")
    (run_dir / "data_card.md").write_text(artifacts["data_card"], encoding="utf-8")

    return {
        "run_dir": str(run_dir),
        "approved": decision.approved,
        "decision": decision.to_dict(),
        "data_validation_passed": validation_report["passed"],
        "native_policy_available": bool(native_policy.get("available")),
        "native_policy_matches_python": bool(native_policy.get("matches_python", False)),
        "openlineage_validation_available": bool(artifacts["openlineage_validation"].get("available")),
        "openlineage_validation_passed": bool(artifacts["openlineage_validation"].get("passed")),
        "run_id": run_context["run_id"],
        "trace_id": run_context["trace_id"],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
