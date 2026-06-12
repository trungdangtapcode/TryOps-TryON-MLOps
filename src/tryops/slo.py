from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tryops.native_burn_rate import evaluate_with_native_burn_rate


SLO_REPORT_SCHEMA = "tryops.slo_burn_rate_report.v1"


def load_slo_config(path: str | Path = "configs/service_level_objectives.json") -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_slo_burn_rates(
    *,
    slo_config: dict[str, Any],
    llm_benchmark: dict[str, Any],
    vton_comparison: dict[str, Any],
    endpoint_smoke: dict[str, Any],
    native_cli_path: str | Path | None = None,
) -> dict[str, Any]:
    workloads = slo_config["workloads"]
    sli_counts = {
        "llm": llm_sli_counts(llm_benchmark, workloads["llm"]),
        "vton": vton_sli_counts(vton_comparison, workloads["vton"]),
        "control_plane": control_plane_sli_counts(endpoint_smoke, workloads["control_plane"]),
    }
    current = {
        name: _evaluate_workload(
            name=name,
            objective=workloads[name],
            windows=slo_config["default_windows"],
            bad_events=counts["bad_events"],
            total_events=counts["total_events"],
            native_cli_path=native_cli_path,
        )
        for name, counts in sli_counts.items()
    }
    drill = _evaluate_workload(
        name="llm-regression-drill",
        objective=workloads["llm"],
        windows=slo_config["default_windows"],
        bad_events=20,
        total_events=100,
        native_cli_path=native_cli_path,
    )
    current_firing = [
        {"workload": workload, "verdict": result.get("verdict")}
        for workload, result in current.items()
        if result.get("verdict") != "ok"
    ]
    return {
        "schema_version": SLO_REPORT_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "period_days": slo_config.get("period_days", 30),
        "slo_config_schema": slo_config.get("schema_version"),
        "sli_counts": sli_counts,
        "current": current,
        "regression_drill": drill,
        "passed": not current_firing and drill.get("verdict") == "page",
        "current_firing": current_firing,
        "native_engine": {
            "available": all(result.get("available") for result in [*current.values(), drill]),
            "schema_version": "tryops.native_burn_rate.v1",
        },
        "notes": [
            "Current windows are computed from local smoke/evaluation artifacts.",
            "The regression drill proves page-level burn-rate alerts fire when both long and short windows are burning.",
        ],
    }


def llm_sli_counts(llm_benchmark: dict[str, Any], objective: dict[str, Any]) -> dict[str, Any]:
    records = llm_benchmark.get("records", [])
    if not records:
        raise ValueError("LLM benchmark must include records")
    latency_max = float(objective["latency_p95_ms_max"])
    quality_min = float(objective["quality_score_min"])
    bad = 0
    reasons: list[dict[str, Any]] = []
    for record in records:
        failed = []
        if float(record.get("latency_ms", 0.0)) > latency_max:
            failed.append("latency")
        if float(record.get("quality_score", 0.0)) < quality_min:
            failed.append("quality")
        if record.get("safety", {}).get("credentials_invented"):
            failed.append("safety")
        if failed:
            bad += 1
            reasons.append({"id": record.get("id", "unknown"), "failed": failed})
    return {
        "total_events": len(records),
        "bad_events": bad,
        "good_events": len(records) - bad,
        "bad_reasons": reasons,
    }


def vton_sli_counts(vton_comparison: dict[str, Any], objective: dict[str, Any]) -> dict[str, Any]:
    runs = vton_comparison.get("runs", [])
    if not runs:
        raise ValueError("VTON comparison must include runs")
    latency_max = float(objective["latency_ms_max"])
    similarity_min = float(objective["garment_similarity_min"])
    bad = 0
    reasons: list[dict[str, Any]] = []
    for run in runs:
        failed = []
        if float(run.get("latency_ms", 0.0)) > latency_max:
            failed.append("latency")
        score = float(run.get("garment_similarity", {}).get("proxy", {}).get("score", 0.0))
        if score < similarity_min:
            failed.append("garment_similarity")
        if failed:
            bad += 1
            reasons.append({"id": run.get("name", "unknown"), "failed": failed})
    return {
        "total_events": len(runs),
        "bad_events": bad,
        "good_events": len(runs) - bad,
        "bad_reasons": reasons,
    }


def control_plane_sli_counts(endpoint_smoke: dict[str, Any], objective: dict[str, Any]) -> dict[str, Any]:
    checks = endpoint_smoke.get("checks", [])
    if not checks:
        raise ValueError("endpoint smoke report must include checks")
    latency_max = float(objective["endpoint_latency_ms_max"])
    bad = 0
    reasons: list[dict[str, Any]] = []
    for check in checks:
        failed = []
        if not bool(check.get("passed", False)):
            failed.append("failed_check")
        if float(check.get("latency_ms", 0.0)) > latency_max:
            failed.append("latency")
        if failed:
            bad += 1
            reasons.append({"id": check.get("name", "unknown"), "failed": failed})
    return {
        "total_events": len(checks),
        "bad_events": bad,
        "good_events": len(checks) - bad,
        "bad_reasons": reasons,
    }


def render_prometheus_burn_rate_rules(slo_config: dict[str, Any]) -> str:
    lines = ["groups:", "- name: tryops-slo-burn-rate-alerts", "  rules:"]
    for workload, objective in slo_config["workloads"].items():
        budget = float(objective["error_budget_ratio"])
        for window in slo_config["default_windows"]:
            alert_name = f"TryOps{_camel(workload)}{_camel(window['name'])}BurnRate"
            long_window = window["long_window"]
            short_window = window["short_window"]
            threshold = float(window["burn_rate_threshold"])
            expr = (
                f'(tryops_slo_error_ratio{{workload="{workload}",window="{long_window}"}} '
                f"> {threshold * budget:.6f}) and "
                f'(tryops_slo_error_ratio{{workload="{workload}",window="{short_window}"}} '
                f"> {threshold * budget:.6f})"
            )
            lines.extend(
                [
                    f"  - alert: {alert_name}",
                    f"    expr: {expr}",
                    "    for: 2m",
                    "    labels:",
                    f"      severity: {window['severity']}",
                    f"      workload: {workload}",
                    "    annotations:",
                    f"      summary: {workload} is burning error budget too quickly",
                    "      runbook_url: docs/service_level_objectives.md",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def _evaluate_workload(
    *,
    name: str,
    objective: dict[str, Any],
    windows: list[dict[str, Any]],
    bad_events: int,
    total_events: int,
    native_cli_path: str | Path | None,
) -> dict[str, Any]:
    native_windows = [
        {
            "name": window["name"],
            "long_bad": bad_events,
            "long_total": total_events,
            "short_bad": bad_events,
            "short_total": total_events,
            "burn_rate_threshold": window["burn_rate_threshold"],
            "severity": window["severity"],
        }
        for window in windows
    ]
    return evaluate_with_native_burn_rate(
        slo_name=name,
        error_budget_ratio=float(objective["error_budget_ratio"]),
        windows=native_windows,
        cli_path=native_cli_path,
    )


def _camel(value: str) -> str:
    return "".join(part.capitalize() for part in str(value).replace("-", "_").split("_"))
