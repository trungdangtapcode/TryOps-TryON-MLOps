from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.alerts import DEFAULT_THRESHOLDS, evaluate_alert_thresholds, render_prometheus_alert_rules  # noqa: E402


class AlertTests(unittest.TestCase):
    def test_alert_thresholds_pass_for_good_metrics(self) -> None:
        report = evaluate_alert_thresholds(
            thresholds=DEFAULT_THRESHOLDS,
            llm_benchmark={"summary": {"latency_p95_ms": 20.0, "quality_score": 1.0}},
            vton_comparison={
                "runs": [
                    {
                        "latency_ms": 200.0,
                        "garment_similarity": {"proxy": {"score": 0.95}},
                    }
                ]
            },
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["firing_alerts"], [])

    def test_alert_thresholds_fire_for_latency_and_quality_regressions(self) -> None:
        report = evaluate_alert_thresholds(
            thresholds=DEFAULT_THRESHOLDS,
            llm_benchmark={"summary": {"latency_p95_ms": 200.0, "quality_score": 0.5}},
            vton_comparison={
                "runs": [
                    {
                        "latency_ms": 6000.0,
                        "garment_similarity": {"proxy": {"score": 0.5}},
                    }
                ]
            },
        )

        self.assertFalse(report["passed"])
        self.assertEqual(len(report["firing_alerts"]), 4)
        self.assertIn("TryOpsLLMLatencyRegression", {alert["alert"] for alert in report["firing_alerts"]})

    def test_prometheus_alert_rules_include_labels_and_annotations(self) -> None:
        rules = render_prometheus_alert_rules(DEFAULT_THRESHOLDS)

        self.assertIn("groups:", rules)
        self.assertIn("alert: TryOpsLLMLatencyRegression", rules)
        self.assertIn("for: 10m", rules)
        self.assertIn("severity: page", rules)
        self.assertIn("annotations:", rules)


if __name__ == "__main__":
    unittest.main()
