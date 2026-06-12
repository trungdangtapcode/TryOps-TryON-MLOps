from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.slo import control_plane_sli_counts, llm_sli_counts, render_prometheus_burn_rate_rules, vton_sli_counts  # noqa: E402


class SLOTests(unittest.TestCase):
    def test_llm_sli_counts_latency_quality_and_safety(self) -> None:
        counts = llm_sli_counts(
            {
                "records": [
                    {"id": "good", "latency_ms": 10, "quality_score": 1.0, "safety": {}},
                    {"id": "bad", "latency_ms": 9999, "quality_score": 0.5, "safety": {"credentials_invented": True}},
                ]
            },
            {"latency_p95_ms_max": 100, "quality_score_min": 0.95},
        )

        self.assertEqual(counts["total_events"], 2)
        self.assertEqual(counts["bad_events"], 1)
        self.assertEqual(counts["bad_reasons"][0]["failed"], ["latency", "quality", "safety"])

    def test_vton_sli_counts_latency_and_similarity(self) -> None:
        counts = vton_sli_counts(
            {
                "runs": [
                    {"name": "ok", "latency_ms": 50, "garment_similarity": {"proxy": {"score": 1.0}}},
                    {"name": "bad", "latency_ms": 99999, "garment_similarity": {"proxy": {"score": 0.2}}},
                ]
            },
            {"latency_ms_max": 1000, "garment_similarity_min": 0.8},
        )

        self.assertEqual(counts["bad_events"], 1)
        self.assertEqual(counts["bad_reasons"][0]["failed"], ["latency", "garment_similarity"])

    def test_control_plane_sli_counts_failures_and_latency(self) -> None:
        counts = control_plane_sli_counts(
            {"checks": [{"name": "ready", "passed": True, "latency_ms": 1}, {"name": "api", "passed": False, "latency_ms": 999}]},
            {"endpoint_latency_ms_max": 100},
        )

        self.assertEqual(counts["total_events"], 2)
        self.assertEqual(counts["bad_events"], 1)
        self.assertEqual(counts["bad_reasons"][0]["failed"], ["failed_check", "latency"])

    def test_prometheus_rules_include_multi_window_conditions(self) -> None:
        rules = render_prometheus_burn_rate_rules(
            {
                "workloads": {"llm": {"error_budget_ratio": 0.01}},
                "default_windows": [
                    {
                        "name": "page_fast",
                        "long_window": "1h",
                        "short_window": "5m",
                        "burn_rate_threshold": 14.4,
                        "severity": "page",
                    }
                ],
            }
        )

        self.assertIn("TryOpsLlmPageFastBurnRate", rules)
        self.assertIn('window="1h"', rules)
        self.assertIn('window="5m"', rules)
        self.assertIn(" and ", rules)


if __name__ == "__main__":
    unittest.main()
