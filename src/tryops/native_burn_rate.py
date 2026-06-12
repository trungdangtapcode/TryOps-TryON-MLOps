from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_BURN_RATE_CLI = Path("artifacts/native/tryops_burn_rate_cli")


def evaluate_with_native_burn_rate(
    *,
    slo_name: str,
    error_budget_ratio: float,
    windows: Sequence[dict[str, Any]],
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    if not windows:
        raise ValueError("windows cannot be empty")
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_BURN_RATE_CLI", DEFAULT_NATIVE_BURN_RATE_CLI))
    if not path.exists():
        return {
            "available": False,
            "cli_path": str(path),
            "reason": "native burn-rate CLI not found",
        }

    payload_lines = [
        f"slo.name={slo_name}",
        f"slo.error_budget_ratio={float(error_budget_ratio)}",
        "windows=" + ",".join(str(window["name"]) for window in windows),
    ]
    for window in windows:
        name = str(window["name"])
        prefix = f"window.{name}."
        payload_lines.extend(
            [
                f"{prefix}long_bad={float(window['long_bad'])}",
                f"{prefix}long_total={float(window['long_total'])}",
                f"{prefix}short_bad={float(window['short_bad'])}",
                f"{prefix}short_total={float(window['short_total'])}",
                f"{prefix}threshold={float(window['burn_rate_threshold'])}",
                f"{prefix}severity={window['severity']}",
            ]
        )
    completed = subprocess.run(
        [str(path)],
        input="\n".join(payload_lines) + "\n",
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return {
            "available": True,
            "cli_path": str(path),
            "returncode": completed.returncode,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    result = json.loads(completed.stdout)
    result["available"] = True
    result["cli_path"] = str(path)
    result["returncode"] = completed.returncode
    return result
