#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_sensitivity import run_llm_sensitivity_benchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark prompt/output length sensitivity for the local LLM baseline.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/llm_sensitivity/sensitivity.json"))
    parser.add_argument("--model-alias", default="baseline")
    parser.add_argument("--prompt-length", type=int, action="append", dest="prompt_lengths")
    parser.add_argument("--output-limit", type=int, action="append", dest="output_limits")
    args = parser.parse_args()

    report = run_llm_sensitivity_benchmark(
        output_path=args.output,
        model_alias=args.model_alias,
        prompt_length_targets=args.prompt_lengths,
        output_token_limits=args.output_limits,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
