from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_THRESHOLDS = {
    "schema_version": "tryops.alert_thresholds.v1",
    "latency": {
        "llm_latency_p95_ms_max": 100.0,
        "vton_latency_ms_max": 5000.0,
    },
    "quality": {
        "llm_quality_score_min": 0.95,
        "vton_garment_similarity_min": 0.8,
    },
}


def load_thresholds(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        return json.loads(json.dumps(DEFAULT_THRESHOLDS))
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_alert_thresholds(
    *,
    thresholds: dict[str, Any],
    llm_benchmark: dict[str, Any],
    vton_comparison: dict[str, Any],
) -> dict[str, Any]:
    latency_thresholds = thresholds.get("latency", {})
    quality_thresholds = thresholds.get("quality", {})
    observed = {
        "llm_latency_p95_ms": _float_at(llm_benchmark, ["summary", "latency_p95_ms"]),
        "llm_quality_score": _float_at(llm_benchmark, ["summary", "quality_score"]),
        "vton_latency_ms": _max_vton_latency(vton_comparison),
        "vton_garment_similarity": _min_vton_garment_similarity(vton_comparison),
    }
    checks = [
        _max_check(
            name="llm_latency_p95_ms",
            observed=observed["llm_latency_p95_ms"],
            threshold=float(latency_thresholds["llm_latency_p95_ms_max"]),
            alert_name="TryOpsLLMLatencyRegression",
        ),
        _max_check(
            name="vton_latency_ms",
            observed=observed["vton_latency_ms"],
            threshold=float(latency_thresholds["vton_latency_ms_max"]),
            alert_name="TryOpsVTONLatencyRegression",
        ),
        _min_check(
            name="llm_quality_score",
            observed=observed["llm_quality_score"],
            threshold=float(quality_thresholds["llm_quality_score_min"]),
            alert_name="TryOpsLLMQualityRegression",
        ),
        _min_check(
            name="vton_garment_similarity",
            observed=observed["vton_garment_similarity"],
            threshold=float(quality_thresholds["vton_garment_similarity_min"]),
            alert_name="TryOpsVTONQualityRegression",
        ),
    ]
    firing = [check for check in checks if check["firing"]]
    return {
        "schema_version": "tryops.alert_report.v1",
        "passed": not firing,
        "observed": observed,
        "thresholds": thresholds,
        "checks": checks,
        "firing_alerts": firing,
    }


def render_prometheus_alert_rules(thresholds: dict[str, Any]) -> str:
    latency = thresholds["latency"]
    quality = thresholds["quality"]
    return "\n".join(
        [
            "groups:",
            "- name: tryops-enterprise-alerts",
            "  rules:",
            "  - alert: TryOpsLLMLatencyRegression",
            f"    expr: tryops_llm_latency_p95_ms > {float(latency['llm_latency_p95_ms_max'])}",
            "    for: 10m",
            "    labels:",
            "      severity: warning",
            "      workload: llm",
            "    annotations:",
            "      summary: LLM latency p95 is above the release threshold",
            "      runbook_url: docs/observability_contract.md",
            "  - alert: TryOpsVTONLatencyRegression",
            f"    expr: tryops_vton_latency_ms > {float(latency['vton_latency_ms_max'])}",
            "    for: 10m",
            "    labels:",
            "      severity: warning",
            "      workload: vton",
            "    annotations:",
            "      summary: VTON latency is above the release threshold",
            "      runbook_url: docs/observability_contract.md",
            "  - alert: TryOpsLLMQualityRegression",
            f"    expr: tryops_llm_quality_score < {float(quality['llm_quality_score_min'])}",
            "    for: 10m",
            "    labels:",
            "      severity: page",
            "      workload: llm",
            "    annotations:",
            "      summary: LLM quality score is below the release threshold",
            "      runbook_url: docs/observability_contract.md",
            "  - alert: TryOpsVTONQualityRegression",
            f"    expr: tryops_vton_garment_similarity < {float(quality['vton_garment_similarity_min'])}",
            "    for: 10m",
            "    labels:",
            "      severity: page",
            "      workload: vton",
            "    annotations:",
            "      summary: VTON garment similarity is below the release threshold",
            "      runbook_url: docs/observability_contract.md",
            "",
        ]
    )


def _max_check(*, name: str, observed: float, threshold: float, alert_name: str) -> dict[str, Any]:
    firing = observed > threshold
    return {
        "alert": alert_name,
        "metric": name,
        "operator": "<=",
        "observed": observed,
        "threshold": threshold,
        "firing": firing,
        "status": "firing" if firing else "ok",
    }


def _min_check(*, name: str, observed: float, threshold: float, alert_name: str) -> dict[str, Any]:
    firing = observed < threshold
    return {
        "alert": alert_name,
        "metric": name,
        "operator": ">=",
        "observed": observed,
        "threshold": threshold,
        "firing": firing,
        "status": "firing" if firing else "ok",
    }


def _float_at(payload: dict[str, Any], path: list[str]) -> float:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"missing field {'.'.join(path)}")
        value = value[key]
    return float(value)


def _max_vton_latency(vton_comparison: dict[str, Any]) -> float:
    runs = vton_comparison.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("vton comparison must include runs")
    return max(float(run["latency_ms"]) for run in runs)


def _min_vton_garment_similarity(vton_comparison: dict[str, Any]) -> float:
    runs = vton_comparison.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("vton comparison must include runs")
    scores = []
    for run in runs:
        garment_similarity = run.get("garment_similarity", {})
        proxy = garment_similarity.get("proxy", {})
        scores.append(float(proxy["score"]))
    return min(scores)
