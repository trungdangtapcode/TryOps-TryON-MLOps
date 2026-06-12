from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tryops.deployment import rollback_release
from tryops.native_burn_rate import evaluate_with_native_burn_rate
from tryops.native_chaos import evaluate_with_native_chaos


CHAOS_REPORT_SCHEMA = "tryops.chaos_drill_report.v1"


DEFAULT_CHAOS_SCENARIOS: list[dict[str, str]] = [
    {"id": "chaos-gpu-oom-vton", "type": "gpu_oom", "workload": "vton"},
    {"id": "chaos-slow-decode-llm", "type": "slow_decode", "workload": "llm"},
    {"id": "chaos-corrupted-weights-llm", "type": "corrupted_weights", "workload": "llm"},
    {"id": "chaos-poisoned-candidate-vton", "type": "poisoned_candidate", "workload": "vton"},
]


def run_chaos_drill(
    *,
    slo_config: dict[str, Any],
    package_id: str,
    packages_dir: str | Path,
    native_chaos_cli: str | Path | None = None,
    native_burn_cli: str | Path | None = None,
    scenarios: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    native_chaos = evaluate_with_native_chaos(
        scenarios or DEFAULT_CHAOS_SCENARIOS,
        cli_path=native_chaos_cli,
    )
    evaluated = []
    rollback_triggers = []
    for scenario in native_chaos.get("scenarios", []):
        workload = str(scenario["workload"])
        objective = slo_config["workloads"].get(workload, slo_config["workloads"]["llm"])
        burn_rate = evaluate_with_native_burn_rate(
            slo_name=f"chaos-{scenario['id']}",
            error_budget_ratio=float(objective["error_budget_ratio"]),
            windows=[
                {
                    "name": window["name"],
                    "long_bad": int(scenario["bad_events"]),
                    "long_total": int(scenario["total_events"]),
                    "short_bad": int(scenario["bad_events"]),
                    "short_total": int(scenario["total_events"]),
                    "burn_rate_threshold": float(window["burn_rate_threshold"]),
                    "severity": window["severity"],
                }
                for window in slo_config["default_windows"]
            ],
            cli_path=native_burn_cli,
        )
        rollback_required = bool(scenario.get("rollback_required")) and burn_rate.get("verdict") == "page"
        evaluated.append(
            {
                "scenario": scenario,
                "burn_rate": burn_rate,
                "rollback_required": rollback_required,
                "steady_state_hypothesis": _steady_state_hypothesis(scenario),
                "result": "rollback_required" if rollback_required else "observed",
            }
        )
        if rollback_required:
            rollback_triggers.append(str(scenario["id"]))

    rollback_record = None
    if rollback_triggers:
        rollback_record = rollback_release(
            package_id=package_id,
            packages_dir=packages_dir,
            reason="auto rollback: chaos burn-rate breach from " + ", ".join(rollback_triggers),
        )
        rollback_record["triggered_by"] = rollback_triggers
        _write_json(Path(packages_dir) / package_id / "auto_rollback_record.json", rollback_record)
        _write_json(
            Path(packages_dir) / "rollback_state.json",
            {
                "schema_version": "tryops.rollback_state.v1",
                "updated_at": rollback_record["created_at"],
                "latest_rollback": rollback_record,
            },
        )

    return {
        "schema_version": CHAOS_REPORT_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "research_basis": {
            "google_sre_multiwindow_burn_rate": "https://sre.google/workbook/alerting-on-slos/",
            "chaos_mesh": "https://chaos-mesh.org/docs/",
            "litmuschaos": "https://litmuschaos.io/",
        },
        "package_id": package_id,
        "native_chaos": native_chaos,
        "scenarios": evaluated,
        "auto_rollback": {
            "triggered": rollback_record is not None,
            "trigger_count": len(rollback_triggers),
            "triggers": rollback_triggers,
            "record": rollback_record or {},
        },
        "passed": bool(evaluated)
        and all(item.get("burn_rate", {}).get("available") for item in evaluated)
        and rollback_record is not None,
        "notes": [
            "Chaos scenarios are deterministic local fault injections mapped to SLI bad-event windows.",
            "The native C++ chaos evaluator classifies failure modes; the native C++ burn-rate engine decides whether the error budget is actively burning.",
            "Auto rollback reuses the existing rollback record and state artifacts.",
        ],
    }


def _steady_state_hypothesis(scenario: dict[str, Any]) -> str:
    workload = str(scenario.get("workload", "workload"))
    expected_signal = str(scenario.get("expected_signal", "slo_signal"))
    return (
        f"{workload} should stay within its SLO; injected {scenario.get('type')} should surface as "
        f"{expected_signal} and trigger rollback if the page burn-rate threshold is crossed."
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
