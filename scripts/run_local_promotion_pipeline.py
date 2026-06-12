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

from tryops.pipelines.promotion import run_local_promotion_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local TryOps promotion pipeline.")
    parser.add_argument("candidate_json", type=Path)
    parser.add_argument("dataset_manifest_json", type=Path)
    parser.add_argument("--stage", default="staging", choices=["staging", "champion"])
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated"))
    args = parser.parse_args()

    candidate_payload = json.loads(args.candidate_json.read_text(encoding="utf-8"))
    dataset_manifest = json.loads(args.dataset_manifest_json.read_text(encoding="utf-8"))
    result = run_local_promotion_pipeline(
        candidate_payload=candidate_payload,
        dataset_manifest=dataset_manifest,
        target_stage=args.stage,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["approved"] and result["data_validation_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

