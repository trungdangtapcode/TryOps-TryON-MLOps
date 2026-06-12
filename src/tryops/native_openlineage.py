from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


NATIVE_OPENLINEAGE_SCHEMA = "tryops.native_openlineage.v1"
DEFAULT_NATIVE_OPENLINEAGE_CLI = Path("artifacts/native/tryops_openlineage_cli")
OPENLINEAGE_RUN_STATES = {"START", "RUNNING", "COMPLETE", "ABORT", "FAIL", "OTHER"}


def validate_openlineage_event(
    event_path: str | Path,
    *,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(event_path)
    cli = Path(str(cli_path or os.environ.get("TRYOPS_NATIVE_OPENLINEAGE_CLI", DEFAULT_NATIVE_OPENLINEAGE_CLI)))
    if cli.exists() and os.access(cli, os.X_OK):
        completed = subprocess.run(
            [str(cli), str(path)],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if completed.returncode in {0, 2}:
            payload = json.loads(completed.stdout)
            payload["available"] = payload.get("schema_version") == NATIVE_OPENLINEAGE_SCHEMA
            payload["source"] = "native_cpp_cli"
            payload["returncode"] = completed.returncode
            payload["cli_path"] = str(cli)
            return payload
        return {
            "schema_version": NATIVE_OPENLINEAGE_SCHEMA,
            "available": True,
            "source": "native_cpp_cli_error",
            "returncode": completed.returncode,
            "cli_path": str(cli),
            "passed": False,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }

    fallback = _python_validate(path)
    fallback["available"] = False
    fallback["source"] = "python_deterministic_fallback"
    fallback["returncode"] = None
    fallback["cli_path"] = str(cli)
    return fallback


def _python_validate(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _report(False, "", "", "", "", 0, 0, ["event file is missing"])
    event = json.loads(path.read_text(encoding="utf-8"))
    event_type = str(event.get("eventType", ""))
    run = event.get("run", {}) if isinstance(event.get("run"), dict) else {}
    job = event.get("job", {}) if isinstance(event.get("job"), dict) else {}
    inputs = event.get("inputs", []) if isinstance(event.get("inputs"), list) else []
    outputs = event.get("outputs", []) if isinstance(event.get("outputs"), list) else []

    reasons: list[str] = []
    if event_type not in OPENLINEAGE_RUN_STATES:
        reasons.append("eventType is missing or not an OpenLineage run state")
    if "T" not in str(event.get("eventTime", "")):
        reasons.append("eventTime is missing or not ISO-like")
    if not str(run.get("runId", "")):
        reasons.append("run.runId is missing")
    if not str(job.get("namespace", "")):
        reasons.append("job.namespace is missing")
    if not str(job.get("name", "")):
        reasons.append("job.name is missing")
    if not str(event.get("producer", "")):
        reasons.append("producer is missing")
    if "RunEvent" not in str(event.get("schemaURL", "")):
        reasons.append("schemaURL does not reference RunEvent")
    if not inputs:
        reasons.append("inputs section is empty")
    if not outputs:
        reasons.append("outputs section is empty")

    return _report(
        not reasons,
        event_type,
        str(run.get("runId", "")),
        str(job.get("namespace", "")),
        str(job.get("name", "")),
        len(inputs),
        len(outputs),
        reasons,
    )


def _report(
    passed: bool,
    event_type: str,
    run_id: str,
    job_namespace: str,
    job_name: str,
    input_count: int,
    output_count: int,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": NATIVE_OPENLINEAGE_SCHEMA,
        "engine": {"name": "tryops_openlineage", "language": "python", "version": "0.1.0"},
        "passed": passed,
        "event_type": event_type,
        "run_id": run_id,
        "job_namespace": job_namespace,
        "job_name": job_name,
        "input_dataset_count": input_count,
        "output_dataset_count": output_count,
        "reasons": reasons,
    }
