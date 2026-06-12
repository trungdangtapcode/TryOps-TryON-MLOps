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

from tryops.load_test import run_llm_load_test  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local concurrent LLM load test.")
    parser.add_argument(
        "--prompt",
        default="Explain why MLOps is the core of TryOps in five bullet points.",
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--requests", type=int, default=12)
    parser.add_argument("--model-alias", default="baseline")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/llm_load/load_test.json"))
    args = parser.parse_args()

    report = run_llm_load_test(
        prompt=args.prompt,
        concurrency=args.concurrency,
        requests=args.requests,
        output_path=args.output,
        model_alias=args.model_alias,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
