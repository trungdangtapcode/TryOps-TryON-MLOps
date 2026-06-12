#!/usr/bin/env python3
"""Run the LLM quantization Pareto sweep (R2 tranche).

Sweeps fp16/8bit/4bit variants of one base model, measures real latency, decode
throughput, peak VRAM, and rubric quality, gates each variant with the native
C++ SLO engine, and writes a ``tryops.llm_pareto.v1`` artifact. Degrades to the
deterministic baseline when torch/bitsandbytes/GPU are unavailable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_pareto import run_llm_pareto  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM quantization Pareto frontier sweep.")
    parser.add_argument("--prompt-set", type=Path, default=Path("samples/eval/golden_prompts.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/llm_pareto/pareto.json"))
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--variants", default="none,8bit,4bit")
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--latency-p95-ms-max", type=float, default=10000.0)
    parser.add_argument("--tokens-per-second-min", type=float, default=5.0)
    args = parser.parse_args()

    report = run_llm_pareto(
        prompt_set_path=args.prompt_set,
        output_path=args.output,
        model_id=args.model_id,
        variants=tuple(v.strip() for v in args.variants.split(",") if v.strip()),
        max_tokens=args.max_tokens,
        latency_p95_ms_max=args.latency_p95_ms_max,
        tokens_per_second_min=args.tokens_per_second_min,
    )

    print(f"model: {report['model_id']}")
    for v in report["variants"]:
        if v.get("available"):
            print(
                f"  {v['variant']:>5}: quality={v['quality_score']:.3f} "
                f"tps={v['tokens_per_second']:.1f} vram={v['peak_vram_gb']:.3f}GB "
                f"p50={v['latency_p50_ms']:.0f}ms slo={v['slo'].get('verdict')}"
            )
        else:
            print(f"  {v['variant']:>5}: unavailable ({v.get('error')})")
    print(f"pareto frontier: {report['pareto_frontier']}")
    print(f"recommendation: {report['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
