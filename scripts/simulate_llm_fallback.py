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

from tryops.routing import build_routing_decision  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate LLM fallback routing from optimized aliases to baseline.")
    parser.add_argument("--request-id", default="req-llm-fallback-demo")
    parser.add_argument("--requested-alias", default="challenger")
    parser.add_argument("--optimized-status", default="unavailable")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/llm_fallback/fallback.json"))
    args = parser.parse_args()

    decision = build_routing_decision(
        workload="llm",
        request_id=args.request_id,
        requested_alias=args.requested_alias,
        fallback_enabled=True,
        route_health={
            "baseline": "ready",
            args.requested_alias: args.optimized_status,
        },
    )
    report = {
        "schema_version": "tryops.llm_fallback.v1",
        "request_id": args.request_id,
        "requested_alias": args.requested_alias,
        "optimized_status": args.optimized_status,
        "routing": decision,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
