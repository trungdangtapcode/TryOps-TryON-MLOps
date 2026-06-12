from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NATIVE_QUOTA_CLI = ROOT / "artifacts" / "native" / "tryops-gateway"


def evaluate_native_quota_batch(
    requests: list[dict[str, Any]],
    *,
    native_cli: str | Path | None = None,
) -> dict[str, Any]:
    cli = _native_cli_path(native_cli)
    if not cli.exists():
        return {
            "schema_version": "tryops.native_quota_batch.v1",
            "engine": "native_rust_gateway",
            "available": False,
            "reason": f"native quota gateway binary not found at {cli}",
            "decisions": [],
            "snapshot": {"schema_version": "tryops.quota_snapshot.v1", "engine": "python_fallback", "usage": []},
        }

    payload = {"requests": requests}
    try:
        completed = subprocess.run(
            [str(cli), "quota-check"],
            input=json.dumps(payload),
            text=True,
            check=True,
            capture_output=True,
            timeout=5,
        )
        result = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {
            "schema_version": "tryops.native_quota_batch.v1",
            "engine": "native_rust_gateway",
            "available": False,
            "reason": str(exc),
            "decisions": [],
            "snapshot": {"schema_version": "tryops.quota_snapshot.v1", "engine": "python_fallback", "usage": []},
        }

    result.setdefault("schema_version", "tryops.native_quota_batch.v1")
    result.setdefault("engine", "native_rust_gateway")
    result["available"] = bool(result.get("available", True))
    return result


def _native_cli_path(native_cli: str | Path | None) -> Path:
    if native_cli is not None:
        return Path(native_cli)
    configured = os.getenv("TRYOPS_NATIVE_QUOTA_CLI", "").strip()
    return Path(configured) if configured else DEFAULT_NATIVE_QUOTA_CLI
