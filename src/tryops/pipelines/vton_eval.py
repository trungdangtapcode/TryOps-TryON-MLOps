from __future__ import annotations

from statistics import mean
from typing import Any


def summarize_vton_results(records: list[dict[str, Any]]) -> dict[str, float]:
    """Summarize VTON evaluation records into promotion metrics."""

    if not records:
        raise ValueError("records cannot be empty")

    return {
        "garment_fidelity": _metric(_avg(records, "garment_fidelity")),
        "identity_preservation": _metric(_avg(records, "identity_preservation")),
        "artifact_rate": _metric(_avg(records, "artifact_flag")),
        "latency_p95_ms": _metric(_percentile([float(item["latency_ms"]) for item in records], 0.95)),
    }


def _avg(records: list[dict[str, Any]], key: str) -> float:
    return float(mean(float(item[key]) for item in records))


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return float(ordered[index])


def _metric(value: float) -> float:
    return round(float(value), 6)
