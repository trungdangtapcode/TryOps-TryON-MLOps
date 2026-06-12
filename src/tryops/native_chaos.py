from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


NATIVE_CHAOS_SCHEMA = "tryops.native_chaos.v1"
DEFAULT_NATIVE_CHAOS_CLI = Path("artifacts/native/tryops_chaos_cli")


def evaluate_with_native_chaos(
    scenarios: Sequence[dict[str, Any]],
    *,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    cli = Path(str(cli_path or os.environ.get("TRYOPS_NATIVE_CHAOS_CLI", DEFAULT_NATIVE_CHAOS_CLI)))
    if cli.exists() and os.access(cli, os.X_OK):
        completed = subprocess.run(
            [str(cli)],
            input=_wire_payload(scenarios),
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            payload["available"] = payload.get("schema_version") == NATIVE_CHAOS_SCHEMA
            payload["source"] = "native_cpp_cli"
            payload["returncode"] = completed.returncode
            payload["cli_path"] = str(cli)
            return payload
        return {
            "schema_version": NATIVE_CHAOS_SCHEMA,
            "available": True,
            "source": "native_cpp_cli_error",
            "returncode": completed.returncode,
            "cli_path": str(cli),
            "passed": False,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    fallback = _python_chaos(scenarios)
    fallback["available"] = False
    fallback["source"] = "python_deterministic_fallback"
    fallback["returncode"] = None
    fallback["cli_path"] = str(cli)
    return fallback


def _wire_payload(scenarios: Sequence[dict[str, Any]]) -> str:
    lines = [f"scenario_count={len(scenarios)}"]
    for index, scenario in enumerate(scenarios):
        prefix = f"scenario.{index}."
        lines.extend(
            [
                f"{prefix}id={_wire_value(scenario.get('id', f'scenario-{index}'))}",
                f"{prefix}type={_wire_value(scenario.get('type', 'unknown'))}",
                f"{prefix}workload={_wire_value(scenario.get('workload', 'llm'))}",
            ]
        )
    return "\n".join(lines) + "\n"


def _wire_value(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _python_chaos(scenarios: Sequence[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for scenario in scenarios:
        scenario_type = str(scenario.get("type", "")).lower()
        workload = str(scenario.get("workload", "llm")).lower()
        if scenario_type == "gpu_oom":
            result = _scenario(scenario, workload, "resource_exhaustion", "oom_rejections_and_timeout_spike", 30)
        elif scenario_type == "slow_decode":
            result = _scenario(scenario, workload, "latency_regression", "decode_latency_p95_breach", 20)
        elif scenario_type == "corrupted_weights":
            result = _scenario(scenario, workload, "model_load_failure", "readiness_failure_and_generation_errors", 100)
        elif scenario_type == "poisoned_candidate":
            result = _scenario(scenario, workload, "quality_or_safety_regression", "promotion_or_guardrail_failure", 25)
        else:
            result = _scenario(scenario, workload, "unknown_fault", "manual_review_required", 1, rollback_required=False)
        results.append(result)
    return {
        "schema_version": NATIVE_CHAOS_SCHEMA,
        "engine": {"name": "tryops_chaos", "language": "python", "version": "0.1.0"},
        "passed": bool(results),
        "scenario_count": len(results),
        "rollback_required_count": sum(1 for result in results if result["rollback_required"]),
        "scenarios": results,
    }


def _scenario(
    source: dict[str, Any],
    workload: str,
    failure_mode: str,
    expected_signal: str,
    bad_events: int,
    *,
    rollback_required: bool = True,
) -> dict[str, Any]:
    return {
        "id": str(source.get("id", source.get("type", "scenario"))),
        "type": str(source.get("type", "unknown")).lower(),
        "workload": workload,
        "failure_mode": failure_mode,
        "severity": "page" if rollback_required else "ticket",
        "expected_signal": expected_signal,
        "bad_events": bad_events,
        "total_events": 100,
        "rollback_required": rollback_required,
    }
