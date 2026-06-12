from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from tryops.pipelines.llm_baseline import (
    REAL_MODEL_TARGET,
    estimate_tokens,
    generate_baseline_response,
)
from tryops.run_context import build_run_context


DEFAULT_PROMPT_LENGTH_TARGETS = [16, 64, 256, 1024]
DEFAULT_OUTPUT_TOKEN_LIMITS = [8, 16, 32, 64, 128]


def run_llm_sensitivity_benchmark(
    *,
    output_path: str | Path,
    model_alias: str = "baseline",
    prompt_length_targets: list[int] | None = None,
    output_token_limits: list[int] | None = None,
) -> dict[str, Any]:
    """Measure local LLM behavior across input prompt and output length changes."""

    prompt_targets = prompt_length_targets or DEFAULT_PROMPT_LENGTH_TARGETS
    output_limits = output_token_limits or DEFAULT_OUTPUT_TOKEN_LIMITS
    _validate_positive_integers(prompt_targets, "prompt_length_targets")
    _validate_positive_integers(output_limits, "output_token_limits")

    run_context = build_run_context(run_name="llm-sensitivity-benchmark")
    prompt_records = [
        _run_prompt_length_case(
            target_tokens=target_tokens,
            model_alias=model_alias,
        )
        for target_tokens in prompt_targets
    ]
    output_records = [
        _run_output_length_case(
            max_tokens=max_tokens,
            model_alias=model_alias,
        )
        for max_tokens in output_limits
    ]

    report = {
        "schema_version": "tryops.llm_sensitivity.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "real_model_target": REAL_MODEL_TARGET,
        "model_alias": model_alias,
        "run_context": run_context,
        "prompt_length_sensitivity": prompt_records,
        "output_length_sensitivity": output_records,
        "summary": {
            "prompt_length": _summarize_prompt_records(prompt_records),
            "output_length": _summarize_output_records(output_records),
        },
        "notes": [
            "This is a deterministic local baseline sensitivity report, not a neural vLLM benchmark.",
            "Prompt length approximates prefill pressure; output token limits approximate decode-length pressure.",
            "Run the same report against Transformers, vLLM, GPTQ, AWQ, and GGUF variants before production claims.",
        ],
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def build_prompt_for_target_tokens(target_tokens: int) -> str:
    if target_tokens < 1:
        raise ValueError("target_tokens must be positive")
    prefix = [
        "Explain",
        "why",
        "MLOps",
        "is",
        "the",
        "core",
        "of",
        "TryOps",
        "for",
        "production",
        "LLM",
        "serving.",
    ]
    suffix = ["Include", "governance,", "monitoring,", "reproducibility,", "and", "rollback", "evidence."]
    filler_size = max(0, target_tokens - len(prefix) - len(suffix))
    words = prefix + ["ctx"] * filler_size + suffix
    return " ".join(words[:target_tokens])


def _run_prompt_length_case(*, target_tokens: int, model_alias: str) -> dict[str, Any]:
    prompt = build_prompt_for_target_tokens(target_tokens)
    response = generate_baseline_response(
        prompt=prompt,
        model_alias=model_alias,
        max_tokens=128,
        structured=True,
    )
    return {
        "target_input_tokens": target_tokens,
        "actual_input_tokens": response["prompt"]["estimated_tokens"],
        "input_characters": response["prompt"]["characters"],
        "prompt_class": response["prompt"]["class"],
        "max_tokens": 128,
        "output_tokens": response["output"]["estimated_tokens"],
        "output_truncated": response["output"]["truncated"],
        "latency_ms": response["metrics"]["latency_ms"],
        "tokens_per_second": response["metrics"]["tokens_per_second"],
        "memory_gb": response["metrics"]["memory_gb"],
        "phase_timing": response["metrics"].get("phase_timing", {}),
        "safety_status": response["safety"]["status"],
    }


def _run_output_length_case(*, max_tokens: int, model_alias: str) -> dict[str, Any]:
    prompt = build_prompt_for_target_tokens(128)
    response = generate_baseline_response(
        prompt=prompt,
        model_alias=model_alias,
        max_tokens=max_tokens,
        structured=True,
    )
    return {
        "max_tokens": max_tokens,
        "input_tokens": response["prompt"]["estimated_tokens"],
        "input_characters": response["prompt"]["characters"],
        "prompt_class": response["prompt"]["class"],
        "output_tokens": response["output"]["estimated_tokens"],
        "output_truncated": response["output"]["truncated"],
        "latency_ms": response["metrics"]["latency_ms"],
        "tokens_per_second": response["metrics"]["tokens_per_second"],
        "memory_gb": response["metrics"]["memory_gb"],
        "phase_timing": response["metrics"].get("phase_timing", {}),
        "safety_status": response["safety"]["status"],
    }


def _summarize_prompt_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_records = sorted(records, key=lambda item: int(item["actual_input_tokens"]))
    latencies = [float(item["latency_ms"]) for item in sorted_records]
    memories = [float(item["memory_gb"]) for item in sorted_records]
    return {
        "min_input_tokens": int(sorted_records[0]["actual_input_tokens"]),
        "max_input_tokens": int(sorted_records[-1]["actual_input_tokens"]),
        "avg_latency_ms": _metric(mean(latencies)),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_ms_per_1k_input_tokens": _metric(
            _slope(
                x1=float(sorted_records[0]["actual_input_tokens"]),
                y1=float(sorted_records[0]["latency_ms"]),
                x2=float(sorted_records[-1]["actual_input_tokens"]),
                y2=float(sorted_records[-1]["latency_ms"]),
            )
            * 1000.0
        ),
        "long_short_latency_ratio": _ratio(float(sorted_records[-1]["latency_ms"]), float(sorted_records[0]["latency_ms"])),
        "max_memory_gb": _metric(max(memories)),
    }


def _summarize_output_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_records = sorted(records, key=lambda item: int(item["max_tokens"]))
    latencies = [float(item["latency_ms"]) for item in sorted_records]
    memories = [float(item["memory_gb"]) for item in sorted_records]
    return {
        "min_max_tokens": int(sorted_records[0]["max_tokens"]),
        "max_max_tokens": int(sorted_records[-1]["max_tokens"]),
        "min_observed_output_tokens": min(int(item["output_tokens"]) for item in sorted_records),
        "max_observed_output_tokens": max(int(item["output_tokens"]) for item in sorted_records),
        "truncated_cases": sum(1 for item in sorted_records if bool(item["output_truncated"])),
        "avg_latency_ms": _metric(mean(latencies)),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_ms_per_100_output_tokens": _metric(
            _slope(
                x1=float(sorted_records[0]["output_tokens"]),
                y1=float(sorted_records[0]["latency_ms"]),
                x2=float(sorted_records[-1]["output_tokens"]),
                y2=float(sorted_records[-1]["latency_ms"]),
            )
            * 100.0
        ),
        "max_memory_gb": _metric(max(memories)),
    }


def _validate_positive_integers(values: list[int], field_name: str) -> None:
    if not values:
        raise ValueError(f"{field_name} cannot be empty")
    if any(value < 1 for value in values):
        raise ValueError(f"{field_name} must contain positive integers")


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return _metric(float(ordered[index]))


def _slope(*, x1: float, y1: float, x2: float, y2: float) -> float:
    if x2 == x1:
        return 0.0
    return (y2 - y1) / (x2 - x1)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return _metric(numerator / denominator)


def _metric(value: float) -> float:
    return round(float(value), 6)
