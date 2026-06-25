#!/usr/bin/env python3
"""Run the real Transformers-backed LLM benchmark (R1 tranche)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_benchmark import run_llm_benchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the real TryOps LLM via Transformers.")
    parser.add_argument("--prompt-set", type=Path, default=Path("samples/eval/golden_prompts.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/llm_real/benchmark.json"))
    parser.add_argument("--model-alias", default="champion")
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()

    report = run_llm_benchmark(
        prompt_set_path=args.prompt_set,
        output_path=args.output,
        model_alias=args.model_alias,
        max_tokens=args.max_tokens,
        adapter="real",
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    adapters = {r["model"].get("adapter") for r in report["records"]}
    print(f"adapters used: {sorted(adapters)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
