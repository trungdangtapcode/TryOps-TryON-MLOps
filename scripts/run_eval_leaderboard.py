#!/usr/bin/env python3
"""Build the Theme-N eval leaderboard.

Re-scores benchmark records with a model-agnostic rubric + LLM-as-judge, computes
bootstrap quality CIs and judge/rubric agreement, and enriches with the real
Pareto and energy artifacts when present. Offline-safe: the judge degrades to the
rubric without an API key.
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

from tryops.pipelines.eval_leaderboard import run_eval_leaderboard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Theme-N eval leaderboard.")
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        default=["artifacts/eval/llm_baseline/benchmark.json"],
        help="One or more tryops.llm_benchmark.v1 artifacts (per-record).",
    )
    parser.add_argument("--pareto", default="artifacts/eval/llm_pareto/pareto.json")
    parser.add_argument("--energy", default="artifacts/eval/energy/energy_sweep.json")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/leaderboard/leaderboard.json"))
    args = parser.parse_args()

    report = run_eval_leaderboard(
        benchmark_paths=args.benchmarks,
        output_path=args.output,
        pareto_path=args.pareto,
        energy_path=args.energy,
    )
    print(f"judge backend: {report['judge_backend']}")
    print(f"ranking: {report['ranking']}")
    for row in report["leaderboard"]:
        ci = row.get("quality_ci")
        q = (f"q={row['quality']:.3f} [{ci['ci_lo']:.3f},{ci['ci_hi']:.3f}] k={row.get('judge_rubric_kappa')}"
             if ci else f"q={row.get('quality')}")
        extra = []
        if row.get("tokens_per_second") is not None:
            extra.append(f"tps={row['tokens_per_second']:.1f}")
        if row.get("peak_vram_gb") is not None:
            extra.append(f"vram={row['peak_vram_gb']:.2f}GB")
        if row.get("energy_wh_per_1k_tokens") is not None:
            extra.append(f"{row['energy_wh_per_1k_tokens']:.3f}Wh/1k")
        if row.get("slo_verdict"):
            extra.append(f"slo={row['slo_verdict']}")
        print(f"  {row['variant']:>8}: {q}  {' '.join(extra)}")
    sig = report.get("top_two_significance")
    if sig:
        print(f"top-2 significance ({sig['variant_a']} vs {sig['variant_b']}): "
              f"diff={sig['mean_diff']} significant={sig['significant']} p={sig['p_value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
