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

from tryops.native_quota import evaluate_native_quota_batch  # noqa: E402
from tryops.quota import check_and_record_quota, quota_snapshot, reset_quota_usage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate usage-based quota accounting.")
    parser.add_argument("--user-id", default="demo-user")
    parser.add_argument("--plan", default="free")
    parser.add_argument("--llm-requests", type=int, default=3)
    parser.add_argument("--llm-estimated-tokens", type=int, default=300)
    parser.add_argument("--vton-requests", type=int, default=2)
    parser.add_argument("--native-cli", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/quota/quota_usage.json"))
    args = parser.parse_args()

    requests = [
        {
            "user_id": args.user_id,
            "plan": args.plan,
            "workload": "llm",
            "request_units": 1,
            "estimated_tokens": args.llm_estimated_tokens,
        }
        for _ in range(args.llm_requests)
    ] + [
        {
            "user_id": args.user_id,
            "plan": args.plan,
            "workload": "vton",
            "request_units": 1,
        }
        for _ in range(args.vton_requests)
    ]

    native_quota = evaluate_native_quota_batch(requests, native_cli=args.native_cli)
    if native_quota["available"]:
        decisions = native_quota["decisions"]
        snapshot = native_quota["snapshot"]
    else:
        reset_quota_usage()
        decisions = []
        for request in requests:
            decisions.append(
                check_and_record_quota(
                    user_id=str(request["user_id"]),
                    plan=str(request["plan"]),
                    workload=str(request["workload"]),
                    request_units=int(request.get("request_units", 1)),
                    estimated_tokens=int(request.get("estimated_tokens", 0)),
                )
            )
        snapshot = quota_snapshot()

    checks = {
        "native_quota_available": native_quota["available"],
        "raw_user_id_not_in_snapshot": args.user_id not in json.dumps(snapshot, sort_keys=True),
        "all_decisions_allowed": all(bool(decision.get("allowed")) for decision in decisions),
        "llm_token_usage_recorded": any(
            row.get("dimension") == "llm_tokens_per_day" and int(row.get("used", 0)) > 0
            for row in snapshot.get("usage", [])
        )
        if isinstance(snapshot, dict)
        else False,
    }

    report = {
        "schema_version": "tryops.quota_simulation.v1",
        "user_id": args.user_id,
        "plan": args.plan,
        "native_quota": {
            "engine": native_quota.get("engine", "native_rust_gateway"),
            "available": native_quota["available"],
            "reason": native_quota.get("reason", "ok"),
        },
        "checks": checks,
        "decisions": decisions,
        "snapshot": snapshot,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
