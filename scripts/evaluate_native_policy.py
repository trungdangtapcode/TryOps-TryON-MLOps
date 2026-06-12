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

from tryops.contracts import ModelCandidate  # noqa: E402
from tryops.native_policy import evaluate_with_native_policy, native_decision_matches_python  # noqa: E402
from tryops.policy import evaluate_promotion  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a candidate with the native C++ policy CLI.")
    parser.add_argument("candidate_json", type=Path)
    parser.add_argument("--stage", default="staging", choices=["staging", "champion"])
    parser.add_argument("--cli", type=Path, default=Path("artifacts/native/tryops_policy_cli"))
    args = parser.parse_args()

    candidate = ModelCandidate.from_dict(json.loads(args.candidate_json.read_text(encoding="utf-8")))
    native = evaluate_with_native_policy(candidate, target_stage=args.stage, cli_path=args.cli)
    python_decision = evaluate_promotion(candidate, target_stage=args.stage)
    matches_python = native_decision_matches_python(native, python_decision)
    result = {
        "candidate_id": candidate.candidate_id,
        "target_stage": args.stage,
        "native": native,
        "python": python_decision.to_dict(),
        "matches_python": matches_python,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if native.get("available") and matches_python else 2


if __name__ == "__main__":
    raise SystemExit(main())
