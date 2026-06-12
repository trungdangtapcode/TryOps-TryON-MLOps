#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.routing import build_experiment_routing_decision  # noqa: E402


VARIANTS = [
    {
        "name": "champion",
        "adapter": "tryops-rule-baseline",
        "allocation_percent": 45.0,
        "impressions": 1000.0,
        "rewards": 820.0,
        "guardrail_block_rate": 0.002,
        "latency_p95_ms": 42.0,
        "error_rate": 0.002,
    },
    {
        "name": "challenger",
        "adapter": "tryops-rule-baseline",
        "allocation_percent": 45.0,
        "impressions": 500.0,
        "rewards": 465.0,
        "guardrail_block_rate": 0.004,
        "latency_p95_ms": 38.0,
        "error_rate": 0.003,
    },
    {
        "name": "candidate",
        "adapter": "tryops-rule-baseline",
        "allocation_percent": 10.0,
        "impressions": 50.0,
        "rewards": 49.0,
        "guardrail_block_rate": 0.080,
        "latency_p95_ms": 35.0,
        "error_rate": 0.003,
    },
]

THRESHOLDS = {
    "max_block_rate": 0.02,
    "max_latency_p95_ms": 120.0,
    "max_error_rate": 0.01,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an online experiment routing sample.")
    parser.add_argument("--native-cli", type=Path, default=Path("artifacts/native/tryops_experiment_router_cli"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/experiments/online_experiment_report.json"))
    args = parser.parse_args()

    ab_decision = build_experiment_routing_decision(
        workload="llm",
        request_id="tryops-online-ab-0007",
        experiment_id="tryops-llm-answer-quality",
        variants=VARIANTS,
        mode="ab",
        holdback_percent=5.0,
        guardrail_thresholds=THRESHOLDS,
        cli_path=str(args.native_cli),
    )
    bandit_decision = build_experiment_routing_decision(
        workload="llm",
        request_id="tryops-online-bandit-0001",
        experiment_id="tryops-llm-answer-quality",
        variants=VARIANTS,
        mode="bandit",
        holdback_percent=5.0,
        guardrail_thresholds=THRESHOLDS,
        cli_path=str(args.native_cli),
    )

    ab_route = ab_decision["experiment"]
    bandit_route = bandit_decision["experiment"]
    ab_candidate = _variant(ab_route, "candidate")
    bandit_candidate = _variant(bandit_route, "candidate")
    bandit_champion = _variant(bandit_route, "champion")
    bandit_challenger = _variant(bandit_route, "challenger")
    checks = {
        "native_router_available": bool(bandit_route.get("available")) and bandit_route.get("source") == "native_cpp_cli",
        "candidate_guardrail_blocked": (not bandit_candidate["eligible"])
        and "guardrail_block_rate" in bandit_candidate["violations"],
        "ab_candidate_guardrail_blocked": not ab_candidate["eligible"],
        "bandit_shifted_to_challenger": bandit_challenger["traffic_percent"] > bandit_champion["traffic_percent"],
        "bandit_selected_challenger": bandit_decision["primary_alias"] == "challenger"
        and not bandit_route["holdback"],
        "routing_layer_resolved_alias": bandit_decision["primary_alias"] in {"champion", "challenger", "candidate"},
    }
    report = {
        "schema_version": "tryops.online_experiment_report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "native_cli": str(args.native_cli),
        "algorithm": "guarded_ucb_bandit",
        "workload": "llm",
        "guardrail_thresholds": THRESHOLDS,
        "variant_inputs": VARIANTS,
        "decisions": {
            "ab": ab_decision,
            "bandit": bandit_decision,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": checks}, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


def _variant(route: dict[str, object], name: str) -> dict[str, object]:
    for variant in route["variants"]:  # type: ignore[index]
        if variant["name"] == name:
            return variant
    raise KeyError(name)


if __name__ == "__main__":
    raise SystemExit(main())
