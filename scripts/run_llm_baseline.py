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

from tryops.pipelines.llm_baseline import generate_baseline_response  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local TryOps LLM baseline.")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Explain why MLOps is the core of TryOps in five bullet points.",
    )
    parser.add_argument("--model-alias", default="baseline")
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    response = generate_baseline_response(
        prompt=args.prompt,
        model_alias=args.model_alias,
        max_tokens=args.max_tokens,
        structured=True,
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
