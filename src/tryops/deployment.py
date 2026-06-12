from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tryops.gitops import build_gitops_manifests
from tryops.native_gitops import validate_gitops_manifests
from tryops.run_context import build_run_context


def build_deployment_package(
    *,
    promotion_run_dir: str | Path,
    output_dir: str | Path,
    profile: str,
    previous_candidate_id: str | None = None,
) -> dict[str, Any]:
    """Create a local deployment package from promotion evidence artifacts."""

    if profile not in {"staging", "production-demo"}:
        raise ValueError("profile must be 'staging' or 'production-demo'")

    run_dir = Path(promotion_run_dir)
    decision = _read_json(run_dir / "promotion_decision.json")
    registry = _read_json(run_dir / "registry_entry.json")
    lineage = _read_json(run_dir / "lineage.json")
    openlineage_event = (
        _read_json(run_dir / "openlineage_run_event.json")
        if (run_dir / "openlineage_run_event.json").exists()
        else {}
    )
    openlineage_validation = (
        _read_json(run_dir / "openlineage_validation.json")
        if (run_dir / "openlineage_validation.json").exists()
        else {"available": False, "passed": False, "reason": "OpenLineage validation evidence not found"}
    )
    native_policy = (
        _read_json(run_dir / "native_policy_decision.json")
        if (run_dir / "native_policy_decision.json").exists()
        else {"available": False, "reason": "native policy evidence not found"}
    )
    policy_candidate = (
        _read_json(run_dir / "policy_candidate.json")
        if (run_dir / "policy_candidate.json").exists()
        else {}
    )
    run_context = _read_json(run_dir / "run_context.json") if (run_dir / "run_context.json").exists() else {}
    if not decision.get("approved", False):
        raise ValueError("cannot package a rejected promotion decision")

    package_id = f"{registry['candidate_id']}-{profile}"
    package_dir = Path(output_dir) / package_id
    package_dir.mkdir(parents=True, exist_ok=True)
    deployment_context = build_run_context(
        run_name="deployment-packaging",
        trace_id=f"trace-deploy-{registry['candidate_id']}-{profile}",
    )
    manifest = {
        "schema_version": "tryops.deployment_package.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "package_id": package_id,
        "profile": profile,
        "candidate_id": registry["candidate_id"],
        "model": {
            "name": registry["name"],
            "version": registry["version"],
            "alias": registry["alias"],
            "workload": registry["workload"],
        },
        "routing": {
            "alias": registry["alias"],
            "adapter": _adapter_for_workload(registry["workload"]),
            "release_mode": "manual-approval",
        },
        "promotion_decision": decision,
        "policy_candidate": policy_candidate,
        "native_policy_decision": native_policy,
        "registry_entry": registry,
        "lineage": lineage,
        "openlineage_run_event": openlineage_event,
        "openlineage_validation": openlineage_validation,
        "source_run_context": run_context,
        "deployment_run_context": deployment_context,
        "artifact_uris": dict(registry.get("artifact_uris", {})),
        "gitops": {},
        "checks": {
            "promotion_approved": bool(decision.get("approved")),
            "model_card_present": (run_dir / "model_card.md").exists(),
            "data_card_present": (run_dir / "data_card.md").exists(),
            "registry_entry_present": True,
            "lineage_present": True,
            "openlineage_event_present": bool(openlineage_event),
            "openlineage_validation_passed": bool(openlineage_validation.get("passed")),
            "gitops_manifests_present": False,
            "gitops_validation_passed": False,
            "native_policy_checked": bool(native_policy.get("available")),
            "native_policy_matches_python": bool(native_policy.get("matches_python", False)),
            "policy_candidate_present": bool(policy_candidate),
        },
    }
    gitops_bundle = build_gitops_manifests(deployment_manifest=manifest)
    gitops_dir = package_dir / "gitops"
    for filename, content in gitops_bundle["files"].items():
        _write_text(gitops_dir / filename, content)
    gitops_summary = {
        key: value for key, value in gitops_bundle.items() if key != "files"
    }
    gitops_summary["dir"] = str(gitops_dir)
    gitops_summary["files"] = sorted(gitops_bundle["files"])
    gitops_validation = validate_gitops_manifests(gitops_dir, candidate_id=manifest["candidate_id"])
    _write_json(gitops_dir / "gitops_summary.json", gitops_summary)
    _write_json(gitops_dir / "gitops_validation.json", gitops_validation)
    manifest["gitops"] = gitops_summary
    manifest["gitops_validation"] = gitops_validation
    manifest["checks"]["gitops_manifests_present"] = all((gitops_dir / filename).exists() for filename in gitops_bundle["files"])
    manifest["checks"]["gitops_validation_passed"] = bool(gitops_validation.get("passed"))
    rollback_plan = build_rollback_plan(
        manifest=manifest,
        previous_candidate_id=previous_candidate_id,
    )
    release_notes = render_release_notes(manifest=manifest, rollback_plan=rollback_plan)

    _write_json(package_dir / "deployment_manifest.json", manifest)
    _write_json(package_dir / "rollback_plan.json", rollback_plan)
    (package_dir / "release_notes.md").write_text(release_notes, encoding="utf-8")
    return {
        "package_dir": str(package_dir),
        "manifest": manifest,
        "rollback_plan": rollback_plan,
        "release_notes_path": str(package_dir / "release_notes.md"),
    }


def build_rollback_plan(
    *,
    manifest: dict[str, Any],
    previous_candidate_id: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": "tryops.rollback_plan.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "profile": manifest["profile"],
        "current_candidate_id": manifest["candidate_id"],
        "previous_candidate_id": previous_candidate_id or "manual-selection-required",
        "rollback_strategy": "restore_previous_alias",
        "validation_required": [
            "health_check",
            "readiness_check",
            "golden_prompt_or_image_smoke",
            "promotion_audit_review",
        ],
        "command": (
            "PYTHONPATH=src python scripts/rollback_release.py "
            f"{manifest['package_id']} --packages-dir artifacts/deployments"
        ),
    }


def rollback_release(
    *,
    package_id: str,
    packages_dir: str | Path,
    reason: str,
) -> dict[str, Any]:
    package_dir = Path(packages_dir) / package_id
    manifest = _read_json(package_dir / "deployment_manifest.json")
    rollback_plan = _read_json(package_dir / "rollback_plan.json")
    record = {
        "schema_version": "tryops.rollback_record.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "package_id": package_id,
        "profile": manifest["profile"],
        "rolled_back_candidate_id": manifest["candidate_id"],
        "restored_candidate_id": rollback_plan["previous_candidate_id"],
        "reason": reason,
        "status": "recorded",
    }
    _write_json(package_dir / "rollback_record.json", record)
    _write_json(
        Path(packages_dir) / "rollback_state.json",
        {
            "schema_version": "tryops.rollback_state.v1",
            "updated_at": record["created_at"],
            "latest_rollback": record,
        },
    )
    return record


def render_release_notes(*, manifest: dict[str, Any], rollback_plan: dict[str, Any]) -> str:
    metrics = manifest["registry_entry"].get("metrics", {})
    lines = [
        f"# Release Notes: {manifest['candidate_id']}",
        "",
        f"Profile: `{manifest['profile']}`",
        f"Model: `{manifest['model']['name']}` version `{manifest['model']['version']}`",
        f"Alias: `{manifest['model']['alias']}`",
        f"Workload: `{manifest['model']['workload']}`",
        "",
        "## Promotion Decision",
        "",
        f"- Approved: `{manifest['promotion_decision']['approved']}`",
        f"- Target stage: `{manifest['promotion_decision']['target_stage']}`",
        f"- Reasons: {', '.join(manifest['promotion_decision']['reasons'])}",
        f"- Native policy checked: `{manifest['checks']['native_policy_checked']}`",
        f"- Native/Python policy match: `{manifest['checks']['native_policy_matches_python']}`",
        f"- OpenLineage validation passed: `{manifest['checks']['openlineage_validation_passed']}`",
        f"- GitOps validation passed: `{manifest['checks']['gitops_validation_passed']}`",
        "",
        "## Metrics",
        "",
    ]
    for name, value in sorted(metrics.items()):
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
        ]
    )
    for name, uri in sorted(manifest["artifact_uris"].items()):
        lines.append(f"- `{name}`: `{uri}`")
    lines.extend(
        [
            "",
            "## Rollback",
            "",
            f"- Strategy: `{rollback_plan['rollback_strategy']}`",
            f"- Previous candidate: `{rollback_plan['previous_candidate_id']}`",
            f"- Command: `{rollback_plan['command']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _adapter_for_workload(workload: str) -> str:
    if workload == "vton":
        return "naive-overlay-vton"
    if workload == "llm":
        return "tryops-rule-baseline"
    return "manual-adapter-selection-required"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
