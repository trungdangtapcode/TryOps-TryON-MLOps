from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_experiment_router import route_with_native_experiment_router  # noqa: E402
from tryops.routing import build_experiment_routing_decision  # noqa: E402


def _variants() -> list[dict[str, float | str]]:
    return [
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


class ExperimentRoutingTests(unittest.TestCase):
    def test_python_fallback_blocks_guardrail_violator(self) -> None:
        route = route_with_native_experiment_router(
            _variants(),
            mode="ab",
            request_id="req-ab-001",
            experiment_id="exp",
            holdback_percent=5.0,
            guardrail_thresholds={"max_block_rate": 0.02, "max_latency_p95_ms": 120.0, "max_error_rate": 0.01},
            cli_path=ROOT / "artifacts" / "native" / "missing-experiment-router",
        )
        candidate = _variant(route, "candidate")
        self.assertFalse(route["available"])
        self.assertFalse(candidate["eligible"])
        self.assertIn("guardrail_block_rate", candidate["violations"])
        self.assertEqual(candidate["traffic_percent"], 0.0)

    def test_bandit_weights_better_eligible_variant(self) -> None:
        decision = build_experiment_routing_decision(
            workload="llm",
            request_id="req-bandit-001",
            experiment_id="exp",
            variants=_variants(),
            mode="bandit",
            holdback_percent=5.0,
            guardrail_thresholds={"max_block_rate": 0.02, "max_latency_p95_ms": 120.0, "max_error_rate": 0.01},
            cli_path=str(ROOT / "artifacts" / "native" / "missing-experiment-router"),
        )
        route = decision["experiment"]
        champion = _variant(route, "champion")
        challenger = _variant(route, "challenger")
        candidate = _variant(route, "candidate")

        self.assertEqual(decision["mode"], "experiment_bandit")
        self.assertIn(decision["primary_alias"], {"champion", "challenger"})
        self.assertFalse(candidate["eligible"])
        self.assertGreater(challenger["traffic_percent"], champion["traffic_percent"])


def _variant(route: dict[str, object], name: str) -> dict[str, object]:
    for variant in route["variants"]:  # type: ignore[index]
        if variant["name"] == name:
            return variant
    raise KeyError(name)


if __name__ == "__main__":
    unittest.main()
