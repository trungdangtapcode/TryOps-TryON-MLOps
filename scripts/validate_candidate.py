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
from tryops.policy import evaluate_promotion  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a model candidate promotion gate.")
    parser.add_argument("candidate_json", type=Path)
    parser.add_argument("--stage", default="staging", choices=["staging", "champion"])
    args = parser.parse_args()

    payload = json.loads(args.candidate_json.read_text(encoding="utf-8"))
    candidate = ModelCandidate.from_dict(payload)
    decision = evaluate_promotion(candidate, target_stage=args.stage)
    print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
    return 0 if decision.approved else 2


if __name__ == "__main__":
    raise SystemExit(main())

