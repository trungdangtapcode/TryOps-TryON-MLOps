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

from tryops.orchestration import DEFAULT_NAMESPACE, DEFAULT_PIPELINE_NAME, write_orchestration_skeleton  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TryOps Kubeflow orchestration skeleton artifacts.")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/eval/orchestration"))
    parser.add_argument("--pipeline-name", default=DEFAULT_PIPELINE_NAME)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    args = parser.parse_args()

    report = write_orchestration_skeleton(
        output_dir=args.output_dir,
        pipeline_name=args.pipeline_name,
        namespace=args.namespace,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
