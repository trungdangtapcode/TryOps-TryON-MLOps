from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.energy import (  # noqa: E402
    FALLBACK_ACTIVE_W,
    carbon_aware_gate,
    measure_energy,
)


class MeasureEnergyTests(unittest.TestCase):
    def test_report_shape_and_energy_math(self) -> None:
        # Force the deterministic fallback by sampling a non-GPU device index that
        # NVML can't return — measure_energy still produces a valid report.
        _, report = measure_energy(lambda: sum(range(1000)), tokens=200, device_index=999)
        self.assertEqual(report["schema_version"], "tryops.energy.v1")
        self.assertIn("power_w", report)
        self.assertGreater(report["duration_s"], 0)
        # energy_j == mean_w * duration; energy_wh == energy_j / 3600
        mean_w = report["power_w"]["mean"]
        self.assertAlmostEqual(report["energy_j"], mean_w * report["duration_s"], places=4)
        self.assertAlmostEqual(report["energy_wh"], report["energy_j"] / 3600.0, places=9)
        self.assertIn("energy_wh_per_1k_tokens", report)
        self.assertIn("sci_g_per_1k_tokens", report)

    def test_fallback_trace_uses_active_power(self) -> None:
        _, report = measure_energy(lambda: None, device_index=999)
        # With no GPU the synthesized trace tops out at the active fallback wattage.
        self.assertFalse(report["measured"])
        self.assertEqual(report["source"], "deterministic-fallback")
        self.assertLessEqual(report["power_w"]["peak"], FALLBACK_ACTIVE_W)


class CarbonGateTests(unittest.TestCase):
    def test_pass_within_ceiling_and_regression(self) -> None:
        gate = carbon_aware_gate(
            candidate_energy_wh_per_1k=1.0,
            baseline_energy_wh_per_1k=1.0,
            max_energy_wh_per_1k=2.0,
            max_regression_pct=20.0,
        )
        self.assertEqual(gate["verdict"], "pass")

    def test_fail_on_absolute_ceiling(self) -> None:
        gate = carbon_aware_gate(candidate_energy_wh_per_1k=5.0, max_energy_wh_per_1k=2.0)
        self.assertEqual(gate["verdict"], "fail")
        self.assertTrue(any("ceiling" in r for r in gate["reasons"]))

    def test_fail_on_regression(self) -> None:
        gate = carbon_aware_gate(
            candidate_energy_wh_per_1k=1.5,
            baseline_energy_wh_per_1k=1.0,
            max_regression_pct=20.0,
        )
        self.assertEqual(gate["verdict"], "fail")
        self.assertAlmostEqual(gate["regression_pct"], 50.0, places=3)

    def test_improvement_passes(self) -> None:
        gate = carbon_aware_gate(
            candidate_energy_wh_per_1k=0.5,
            baseline_energy_wh_per_1k=1.0,
            max_regression_pct=20.0,
        )
        self.assertEqual(gate["verdict"], "pass")
        self.assertLess(gate["regression_pct"], 0)


if __name__ == "__main__":
    unittest.main()
