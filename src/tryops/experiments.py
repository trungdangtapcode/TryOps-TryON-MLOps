from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tryops.pipelines.llm_baseline import SUPPORTED_MODEL_ALIASES


DEFAULT_EXPERIMENT_ID = "tryops-llm-answer-quality"
DEFAULT_EXPERIMENT_HOLDBACK_PERCENT = 5.0
DEFAULT_EXPERIMENT_THRESHOLDS = {
    "max_block_rate": 0.02,
    "max_latency_p95_ms": 120.0,
    "max_error_rate": 0.01,
}
DEFAULT_EXPERIMENT_VARIANTS = [
    {
        "name": "champion",
        "adapter": "tryops-rule-baseline",
        "allocation_percent": 45.0,
        "impressions": 1000.0,
        "rewards": 820.0,
        "guardrail_block_rate": 0.002,
        "latency_p95_ms": 42.0,
        "error_rate": 0.002,
    },
    {
        "name": "challenger",
        "adapter": "tryops-rule-baseline",
        "allocation_percent": 45.0,
        "impressions": 500.0,
        "rewards": 465.0,
        "guardrail_block_rate": 0.004,
        "latency_p95_ms": 38.0,
        "error_rate": 0.003,
    },
    {
        "name": "candidate",
        "adapter": "tryops-rule-baseline",
        "allocation_percent": 10.0,
        "impressions": 50.0,
        "rewards": 49.0,
        "guardrail_block_rate": 0.080,
        "latency_p95_ms": 35.0,
        "error_rate": 0.003,
    },
]
DEFAULT_EXPERIMENT_ANALYSIS_VARIANTS = [
    {
        "name": "champion",
        "adapter": "tryops-rule-baseline",
        "allocation_percent": 45.0,
        "impressions": 950.0,
        "rewards": 786.0,
        "guardrail_block_rate": 0.002,
        "latency_p95_ms": 42.0,
        "error_rate": 0.002,
    },
    {
        "name": "challenger",
        "adapter": "tryops-rule-baseline",
        "allocation_percent": 45.0,
        "impressions": 800.0,
        "rewards": 760.0,
        "guardrail_block_rate": 0.004,
        "latency_p95_ms": 38.0,
        "error_rate": 0.003,
    },
]
DEFAULT_EXPERIMENT_HOLDBACK = {
    "name": "champion_holdback",
    "impressions": 1000.0,
    "rewards": 820.0,
}


def normalize_experiment_variants(value: object) -> list[dict[str, Any]]:
    variants = value if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else None
    source = list(variants) if variants else DEFAULT_EXPERIMENT_VARIANTS
    normalized = [_normalize_variant(item) for item in source]
    if not normalized:
        raise ValueError("experiment_variants cannot be empty")
    return normalized


def normalize_experiment_analysis_variants(value: object) -> list[dict[str, Any]]:
    variants = value if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else None
    source = list(variants) if variants else DEFAULT_EXPERIMENT_ANALYSIS_VARIANTS
    normalized = [_normalize_variant(item) for item in source]
    if not normalized:
        raise ValueError("experiment analysis variants cannot be empty")
    return normalized


def normalize_guardrail_thresholds(value: object) -> dict[str, float]:
    thresholds = dict(DEFAULT_EXPERIMENT_THRESHOLDS)
    if isinstance(value, Mapping):
        for key in thresholds:
            if key in value:
                thresholds[key] = _float_field(value, key)
    return thresholds


def normalize_holdback(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return dict(DEFAULT_EXPERIMENT_HOLDBACK)
    return {
        "name": str(value.get("name", DEFAULT_EXPERIMENT_HOLDBACK["name"])),
        "impressions": _float_field(value, "impressions", default=DEFAULT_EXPERIMENT_HOLDBACK["impressions"]),
        "rewards": _float_field(value, "rewards", default=DEFAULT_EXPERIMENT_HOLDBACK["rewards"]),
    }


def _normalize_variant(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("each experiment variant must be an object")
    name = str(value.get("name", "")).strip()
    if name not in SUPPORTED_MODEL_ALIASES:
        raise ValueError(f"unsupported experiment variant '{name}'")
    return {
        "name": name,
        "adapter": str(value.get("adapter", "tryops-rule-baseline")),
        "allocation_percent": _float_field(value, "allocation_percent"),
        "impressions": _float_field(value, "impressions"),
        "rewards": _float_field(value, "rewards"),
        "guardrail_block_rate": _float_field(value, "guardrail_block_rate"),
        "latency_p95_ms": _float_field(value, "latency_p95_ms"),
        "error_rate": _float_field(value, "error_rate"),
    }


def _float_field(source: Mapping[str, Any], key: str, *, default: float = 0.0) -> float:
    try:
        return float(source.get(key, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be numeric") from exc
