from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from tryops.pipelines.llm_baseline import (
    REAL_MODEL_TARGET,
    generate_baseline_response,
    score_expected_characteristics,
)
from tryops.pipelines.llm_phase_timing import summarize_phase_timing
from tryops.run_context import build_run_context


def _select_adapter(adapter: str):
    """Return the generation callable for ``baseline`` or real ``transformers``."""

    if adapter == "baseline":
        return generate_baseline_response
    if adapter in {"real", "transformers"}:
        # Imported lazily so the deterministic spine never requires torch.
        from tryops.pipelines.llm_real import generate_real_response

        return generate_real_response
    raise ValueError(f"unsupported adapter '{adapter}'")


def run_llm_benchmark(
    *,
    prompt_set_path: str | Path,
    output_path: str | Path,
    model_alias: str = "baseline",
    max_tokens: int = 256,
    adapter: str = "baseline",
) -> dict[str, Any]:
    """Run an LLM adapter against a golden prompt set and write a report.

    ``adapter="baseline"`` runs the deterministic stand-in (offline spine);
    ``adapter="real"`` runs the Transformers-backed model on GPU when available,
    emitting the identical ``tryops.llm_benchmark.v1`` shape.
    """

    generate = _select_adapter(adapter)
    run_context = build_run_context(run_name=f"llm-{adapter}-benchmark")
    prompt_set = json.loads(Path(prompt_set_path).read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for item in prompt_set["prompts"]:
        generation = generate(
            prompt=str(item["prompt"]),
            model_alias=model_alias,
            max_tokens=max_tokens,
            structured=True,
        )
        score = score_expected_characteristics(
            generation["output"]["text"],
            list(item.get("expected_characteristics", [])),
        )
        records.append(
            {
                "id": str(item["id"]),
                "prompt": str(item["prompt"]),
                "expected_characteristics": list(item.get("expected_characteristics", [])),
                "output_text": generation["output"]["text"],
                "structured_answer": generation.get("structured_answer", {}),
                "quality_checks": score["checks"],
                "quality_score": score["score"],
                "latency_ms": generation["metrics"]["latency_ms"],
                "tokens_per_second": generation["metrics"]["tokens_per_second"],
                "memory_gb": generation["metrics"]["memory_gb"],
                "phase_timing": generation["metrics"].get("phase_timing", {}),
                "input_tokens": generation["prompt"]["estimated_tokens"],
                "output_tokens": generation["output"]["estimated_tokens"],
                "cost_usd": generation["cost_estimate"]["request_usd"],
                "safety": generation["safety"],
                "model": generation["model"],
            }
        )

    report = {
        "schema_version": "tryops.llm_benchmark.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "prompt_set_id": prompt_set.get("set_id", "unknown"),
        "purpose": prompt_set.get("purpose", "LLM benchmark"),
        "real_model_target": REAL_MODEL_TARGET,
        "adapter": adapter,
        "run_context": run_context,
        "records": records,
        "summary": summarize_llm_benchmark(records),
        "notes": [
            "This report validates the local MLOps contract, not neural answer quality."
            if adapter == "baseline"
            else "Real Transformers inference; metrics are measured on the run hardware.",
            "Compare baseline vs real vs quantized variants for the optimization Pareto frontier.",
        ],
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def summarize_llm_benchmark(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize LLM benchmark records into promotion metrics."""

    if not records:
        raise ValueError("records cannot be empty")

    summary: dict[str, Any] = {
        "quality_score": _metric(mean(float(item["quality_score"]) for item in records)),
        "tokens_per_second": _metric(mean(float(item["tokens_per_second"]) for item in records)),
        "latency_p95_ms": _metric(_percentile([float(item["latency_ms"]) for item in records], 0.95)),
        "memory_gb": _metric(max(float(item["memory_gb"]) for item in records)),
    }
    summary["phase_timing"] = summarize_phase_timing(records)
    return summary


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return float(ordered[index])


def _metric(value: float) -> float:
    return round(float(value), 6)
