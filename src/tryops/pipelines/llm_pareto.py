"""LLM quantization Pareto frontier (R2 tranche).

Sweeps precision/quantization variants of one base model over a prompt set,
measures real latency, decode throughput, peak VRAM, and a rubric quality score,
then computes the quality-vs-cost Pareto frontier. Each variant's per-prompt
latency/throughput samples are gated by the native C++ ``tryops_perf_stats``
engine so the SLO verdict comes from the production-language boundary.

Pure-Python frontier math (:func:`pareto_frontier`) is unit-tested without a GPU;
the GPU sweep marks variants unavailable when torch/bitsandbytes are missing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

from tryops.native_perf_stats import evaluate_with_native_perf_stats
from tryops.pipelines.llm_baseline import score_expected_characteristics
from tryops.run_context import build_run_context

# Default variant sweep. 4-bit/8-bit need bitsandbytes; all share one base model
# so the comparison isolates the effect of quantization.
DEFAULT_VARIANTS = ("none", "8bit", "4bit")


def run_llm_pareto(
    *,
    prompt_set_path: str | Path,
    output_path: str | Path,
    model_id: str = "Qwen/Qwen2.5-0.5B-Instruct",
    variants: Sequence[str] = DEFAULT_VARIANTS,
    max_tokens: int = 96,
    latency_p95_ms_max: float = 10000.0,
    tokens_per_second_min: float = 5.0,
) -> dict[str, Any]:
    """Run the quantization sweep and write a ``tryops.llm_pareto.v1`` artifact."""

    from tryops.pipelines.llm_real import (
        clear_model_cache,
        generate_once,
        load_model,
        real_model_available,
    )

    prompt_set = json.loads(Path(prompt_set_path).read_text(encoding="utf-8"))
    prompts = prompt_set["prompts"]
    run_context = build_run_context(run_name="llm-quantization-pareto")
    variant_reports: list[dict[str, Any]] = []

    for variant in variants:
        record = _run_variant(
            model_id=model_id,
            variant=variant,
            prompts=prompts,
            max_tokens=max_tokens,
            latency_p95_ms_max=latency_p95_ms_max,
            tokens_per_second_min=tokens_per_second_min,
            real_available=real_model_available(),
            load_model=load_model,
            generate_once=generate_once,
            clear_model_cache=clear_model_cache,
        )
        variant_reports.append(record)

    frontier = pareto_frontier(variant_reports)
    report = {
        "schema_version": "tryops.llm_pareto.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "model_id": model_id,
        "run_context": run_context,
        "variants": variant_reports,
        "pareto_frontier": [v["variant"] for v in frontier],
        "recommendation": _recommend(variant_reports),
        "notes": [
            "Quality is a rubric proxy over golden characteristics, not a neural judge.",
            "SLO verdict per variant is computed by the native C++ tryops_perf_stats engine.",
        ],
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _run_variant(
    *,
    model_id: str,
    variant: str,
    prompts: list[dict[str, Any]],
    max_tokens: int,
    latency_p95_ms_max: float,
    tokens_per_second_min: float,
    real_available: bool,
    load_model,
    generate_once,
    clear_model_cache,
) -> dict[str, Any]:
    latencies: list[float] = []
    throughputs: list[float] = []
    vram: list[float] = []
    quality_scores: list[float] = []
    error: str | None = None
    adapter = f"transformers-{variant}"

    if not real_available:
        adapter = "real-transformers-unavailable"
        error = "torch/transformers unavailable"
    else:
        try:
            clear_model_cache()
            tokenizer, model, device = load_model(model_id, variant, cache=False)
            for item in prompts:
                gen = generate_once(
                    tokenizer, model, device, str(item["prompt"]), max_tokens=max_tokens
                )
                latencies.append(gen["latency_ms"])
                throughputs.append(gen["tokens_per_second"])
                vram.append(gen["gpu_memory_gb"])
                quality_scores.append(
                    score_expected_characteristics(
                        gen["text"], list(item.get("expected_characteristics", []))
                    )["score"]
                )
            del model
            clear_model_cache()
        except Exception as exc:  # degraded mode per variant
            error = f"{type(exc).__name__}: {exc}"

    if not latencies:  # unavailable/failure: emit a contract-shaped empty record
        return {
            "variant": variant,
            "adapter": adapter,
            "available": False,
            "error": error,
            "quality_score": 0.0,
            "peak_vram_gb": 0.0,
            "latency_p50_ms": 0.0,
            "tokens_per_second": 0.0,
            "slo": {"verdict": "unknown"},
        }

    native = evaluate_with_native_perf_stats(
        latencies,
        throughputs,
        latency_p95_ms_max=latency_p95_ms_max,
        tokens_per_second_min=tokens_per_second_min,
    )
    return {
        "variant": variant,
        "adapter": adapter,
        "available": True,
        "error": error,
        "quality_score": round(mean(quality_scores), 6),
        "peak_vram_gb": round(max(vram), 6),
        "latency_p50_ms": native.get("latency_ms", {}).get("p50", 0.0),
        "tokens_per_second": round(mean(throughputs), 6),
        "native_perf_stats": native,
        "slo": native.get("slo", {"verdict": "unknown"}),
    }


def pareto_frontier(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return non-dominated variants maximizing quality and throughput while
    minimizing VRAM. A variant is dominated if another is at least as good on
    all three axes and strictly better on one."""

    usable = [v for v in variants if v.get("available")]
    frontier: list[dict[str, Any]] = []
    for candidate in usable:
        dominated = False
        for other in usable:
            if other is candidate:
                continue
            if _dominates(other, candidate):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    not_worse = (
        a["quality_score"] >= b["quality_score"]
        and a["tokens_per_second"] >= b["tokens_per_second"]
        and a["peak_vram_gb"] <= b["peak_vram_gb"]
    )
    strictly_better = (
        a["quality_score"] > b["quality_score"]
        or a["tokens_per_second"] > b["tokens_per_second"]
        or a["peak_vram_gb"] < b["peak_vram_gb"]
    )
    return not_worse and strictly_better


def _recommend(variants: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the smallest-VRAM variant on the frontier that still passes its SLO
    and stays within 2% quality of the best variant (the optimization target)."""

    usable = [v for v in variants if v.get("available")]
    if not usable:
        return {"variant": None, "reason": "no variant produced measurements"}
    best_quality = max(v["quality_score"] for v in usable)
    frontier = pareto_frontier(variants)
    eligible = [
        v
        for v in frontier
        if v.get("slo", {}).get("verdict") == "pass"
        and v["quality_score"] >= best_quality - 0.02
    ]
    pool = eligible or frontier
    choice = min(pool, key=lambda v: v["peak_vram_gb"])
    return {
        "variant": choice["variant"],
        "reason": "smallest VRAM on the Pareto frontier within 2% of best quality and passing SLO",
        "peak_vram_gb": choice["peak_vram_gb"],
        "quality_score": choice["quality_score"],
    }
