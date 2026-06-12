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

from tryops.deployment import build_deployment_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a TryOps deployment package.")
    parser.add_argument("promotion_run_dir", type=Path)
    parser.add_argument("--profile", choices=["staging", "production-demo"], default="staging")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/deployments"))
    parser.add_argument("--previous-candidate-id", default=None)
    args = parser.parse_args()

    result = build_deployment_package(
        promotion_run_dir=args.promotion_run_dir,
        output_dir=args.output_dir,
        profile=args.profile,
        previous_candidate_id=args.previous_candidate_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
