from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.finops import (  # noqa: E402
    FinOpsConfig,
    attach_cache_credit_to_usage,
    build_finops_report,
    build_unit_economics,
    default_semantic_cache_queries,
    entries_from_benchmark,
    evaluate_semantic_cache_workload,
)


class FinOpsTests(unittest.TestCase):
    def test_unit_economics_and_budget_showback_artifacts(self) -> None:
        benchmark = _benchmark()
        config = FinOpsConfig(
            llm_node_hourly_usd=1.0,
            vton_node_hourly_usd=1.0,
            free_daily_budget_usd=0.001,
            team_daily_budget_usd=10.0,
            enterprise_daily_budget_usd=1000.0,
            semantic_cache_threshold=0.60,
        )
        unit = build_unit_economics(benchmark=benchmark, config=config)
        entries = entries_from_benchmark(
            benchmark,
            llm_cost_per_1k_tokens_usd=float(unit["llm"]["cost_per_1k_tokens_usd"]),
            energy_wh_per_1k_tokens=0.5,
        )
        cache_report = evaluate_semantic_cache_workload(
            entries=entries,
            queries=default_semantic_cache_queries(),
            threshold=0.60,
            cli_path="/tmp/missing-tryops-semantic-cache",
        )
        usage_events = attach_cache_credit_to_usage(
            [
                {
                    "tenant_id": "tiny-free",
                    "plan": "free",
                    "active_users": 1,
                    "llm_requests": 20,
                    "llm_tokens": 100000,
                    "vton_requests": 4,
                }
            ],
            cache_report,
        )
        report = build_finops_report(
            benchmark=benchmark,
            quota_report={"snapshot": {"usage": [{"dimension": "llm_tokens_per_day", "used": 100000}]}},
            semantic_cache_report=cache_report,
            usage_events=usage_events,
            config=config,
        )

        self.assertEqual(report["schema_version"], "tryops.finops_report.v1")
        self.assertGreater(report["unit_economics"]["llm"]["cost_per_1k_tokens_usd"], 0.0)
        self.assertTrue(report["semantic_cache"]["passed"])
        self.assertGreaterEqual(report["semantic_cache"]["hit_count"], 2)
        self.assertEqual(report["budget_showback"]["budget_decisions"][0]["action"], "block")
        self.assertFalse(report["promotion_gate_input"]["passed"])


def _benchmark() -> dict[str, object]:
    return {
        "schema_version": "tryops.llm_benchmark.v1",
        "summary": {"tokens_per_second": 1000.0},
        "records": [
            {
                "id": "mlops-summary-001",
                "prompt": "Explain why MLOps is the core of TryOps in five bullet points.",
                "output_text": "Governance registry monitoring reproducibility policy gates.",
                "structured_answer": {"intent": "project_summary", "points": ["Governance"]},
                "input_tokens": 12,
                "output_tokens": 20,
                "latency_ms": 10.0,
                "tokens_per_second": 1000.0,
                "memory_gb": 0.01,
                "model": {"alias": "baseline", "version": "0.1.0"},
                "safety": {"status": "passed"},
            },
            {
                "id": "quantization-001",
                "prompt": "Compare GPTQ and AWQ for an LLM serving benchmark.",
                "output_text": "GPTQ AWQ quantization latency memory quality tradeoffs.",
                "structured_answer": {"intent": "optimization_comparison", "points": ["GPTQ"]},
                "input_tokens": 9,
                "output_tokens": 20,
                "latency_ms": 10.0,
                "tokens_per_second": 1000.0,
                "memory_gb": 0.01,
                "model": {"alias": "baseline", "version": "0.1.0"},
                "safety": {"status": "passed"},
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
