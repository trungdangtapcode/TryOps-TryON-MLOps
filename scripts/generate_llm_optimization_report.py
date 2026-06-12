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

from tryops.pipelines.llm_optimization_report import write_llm_optimization_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the LLM optimization report and Pareto chart.")
    parser.add_argument("--pareto", type=Path, default=Path("artifacts/eval/llm_pareto/pareto.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/eval/llm_optimization_report"))
    args = parser.parse_args()

    report = write_llm_optimization_report(pareto_path=args.pareto, output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
