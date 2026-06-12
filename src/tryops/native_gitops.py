from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


NATIVE_GITOPS_SCHEMA = "tryops.native_gitops.v1"
DEFAULT_NATIVE_GITOPS_CLI = Path("artifacts/native/tryops_gitops_cli")


def validate_gitops_manifests(
    gitops_dir: str | Path,
    *,
    candidate_id: str,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(gitops_dir)
    cli = Path(str(cli_path or os.environ.get("TRYOPS_NATIVE_GITOPS_CLI", DEFAULT_NATIVE_GITOPS_CLI)))
    if cli.exists() and os.access(cli, os.X_OK):
        completed = subprocess.run(
            [str(cli), str(path), candidate_id],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if completed.returncode in {0, 2}:
            payload = json.loads(completed.stdout)
            payload["available"] = payload.get("schema_version") == NATIVE_GITOPS_SCHEMA
            payload["source"] = "native_cpp_cli"
            payload["returncode"] = completed.returncode
            payload["cli_path"] = str(cli)
            return payload
        return {
            "schema_version": NATIVE_GITOPS_SCHEMA,
            "available": True,
            "source": "native_cpp_cli_error",
            "returncode": completed.returncode,
            "cli_path": str(cli),
            "passed": False,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    fallback = _python_validate(path, candidate_id=candidate_id)
    fallback["available"] = False
    fallback["source"] = "python_deterministic_fallback"
    fallback["returncode"] = None
    fallback["cli_path"] = str(cli)
    return fallback


def _python_validate(path: Path, *, candidate_id: str) -> dict[str, Any]:
    files = {
        name: (path / name).read_text(encoding="utf-8") if (path / name).exists() else ""
        for name in ["application.yaml", "rollout.yaml", "services.yaml", "kustomization.yaml"]
    }
    reasons: list[str] = []
    for name, content in files.items():
        if not content:
            reasons.append(f"{name} is missing or empty")

    application = files["application.yaml"]
    rollout = files["rollout.yaml"]
    services = files["services.yaml"]
    kustomization = files["kustomization.yaml"]
    checks = [
        ("kind: Application", application, "Application kind is missing"),
        ("repoURL:", application, "Application source.repoURL is missing"),
        ("syncPolicy:", application, "Application syncPolicy is missing"),
        ("kind: Rollout", rollout, "Rollout kind is missing"),
        ("canary:", rollout, "Rollout canary strategy is missing"),
        ("setWeight:", rollout, "Rollout canary setWeight step is missing"),
        ("pause:", rollout, "Rollout canary pause step is missing"),
        ("kind: Service", services, "Service manifests are missing"),
        ("kind: Kustomization", kustomization, "Kustomization kind is missing"),
        (f"tryops.io/candidate-id: {candidate_id}", application, "Application candidate label is missing"),
        (f"tryops.io/candidate-id: {candidate_id}", rollout, "Rollout candidate label is missing"),
        (f"tryops.io/candidate-id: {candidate_id}", services, "Service candidate label is missing"),
    ]
    for needle, haystack, reason in checks:
        if needle not in haystack:
            reasons.append(reason)

    canary_step_count = rollout.count("setWeight:") + rollout.count("pause:")
    service_count = services.count("kind: Service")
    if canary_step_count < 3:
        reasons.append("Rollout canary strategy has fewer than three setWeight/pause steps")
    if service_count < 2:
        reasons.append("stable and canary Service manifests are both required")

    return {
        "schema_version": NATIVE_GITOPS_SCHEMA,
        "engine": {"name": "tryops_gitops", "language": "python", "version": "0.1.0"},
        "passed": not reasons,
        "manifest_count": sum(1 for content in files.values() if content),
        "canary_step_count": canary_step_count,
        "service_count": service_count,
        "reasons": reasons,
    }
