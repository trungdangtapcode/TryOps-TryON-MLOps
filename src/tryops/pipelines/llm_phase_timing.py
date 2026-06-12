from __future__ import annotations

from typing import Any


PHASE_TIMING_SCHEMA = "tryops.llm_phase_timing.v1"


def build_phase_timing(
    *,
    input_tokens: int,
    output_tokens: int,
    prefill_ms: float,
    decode_ms: float,
    source: str,
    semantics: str,
    total_latency_ms: float | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    prefill = max(0.001, float(prefill_ms))
    decode = max(0.001, float(decode_ms))
    total_phase_ms = prefill + decode
    observed_total = float(total_latency_ms) if total_latency_ms is not None else total_phase_ms
    input_count = max(1, int(input_tokens))
    output_count = max(1, int(output_tokens))
    return {
        "schema_version": PHASE_TIMING_SCHEMA,
        "available": True,
        "source": source,
        "semantics": semantics,
        "prefill_ms": _metric(prefill),
        "decode_ms": _metric(decode),
        "total_phase_ms": _metric(total_phase_ms),
        "total_latency_ms": _metric(max(0.001, observed_total)),
        "input_tokens": input_count,
        "output_tokens": output_count,
        "prefill_tokens_per_second": _metric(input_count / max(prefill / 1000.0, 0.001)),
        "decode_tokens_per_second": _metric(output_count / max(decode / 1000.0, 0.001)),
        "prefill_ms_per_input_token": _metric(prefill / input_count),
        "decode_ms_per_output_token": _metric(decode / output_count),
        "notes": list(notes or []),
    }


def summarize_phase_timing(records: list[dict[str, Any]]) -> dict[str, Any]:
    timings = [
        record.get("phase_timing", {})
        for record in records
        if isinstance(record.get("phase_timing"), dict) and record["phase_timing"].get("available")
    ]
    if not timings:
        return {"schema_version": PHASE_TIMING_SCHEMA, "available": False}
    prefill_values = [float(item["prefill_ms"]) for item in timings]
    decode_values = [float(item["decode_ms"]) for item in timings]
    return {
        "schema_version": PHASE_TIMING_SCHEMA,
        "available": True,
        "record_count": len(timings),
        "prefill_avg_ms": _metric(sum(prefill_values) / len(prefill_values)),
        "prefill_p95_ms": _metric(_percentile(prefill_values, 0.95)),
        "decode_avg_ms": _metric(sum(decode_values) / len(decode_values)),
        "decode_p95_ms": _metric(_percentile(decode_values, 0.95)),
        "sources": sorted({str(item.get("source", "unknown")) for item in timings}),
        "semantics": sorted({str(item.get("semantics", "unknown")) for item in timings}),
    }


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return float(ordered[index])


def _metric(value: float) -> float:
    return round(float(value), 6)
