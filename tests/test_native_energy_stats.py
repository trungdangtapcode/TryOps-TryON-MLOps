from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_energy_stats import evaluate_with_native_energy_stats  # noqa: E402

CLI_PATH = ROOT / "artifacts" / "native" / "tryops_energy_stats_cli"


class NativeEnergyBridgeTests(unittest.TestCase):
    def test_empty_samples_raises(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_with_native_energy_stats([], 1.0)

    def test_nonpositive_duration_raises(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_with_native_energy_stats([10.0], 0.0)

    def test_missing_cli_degrades_gracefully(self) -> None:
        result = evaluate_with_native_energy_stats(
            [10.0, 20.0], 1.0, cli_path=ROOT / "artifacts" / "native" / "nope"
        )
        self.assertFalse(result["available"])


@unittest.skipUnless(CLI_PATH.exists(), "native energy stats CLI not built")
class NativeEnergyEngineTests(unittest.TestCase):
    def test_energy_math_and_intensities(self) -> None:
        # mean power 100 W over 10 s => 1000 J => 1000/3600 Wh.
        result = evaluate_with_native_energy_stats(
            [100.0, 100.0], 10.0, tokens=1000, grid_intensity_g_per_kwh=475.0
        )
        self.assertTrue(result["available"])
        self.assertAlmostEqual(result["energy_j"], 1000.0, places=3)
        self.assertAlmostEqual(result["energy_wh"], 1000.0 / 3600.0, places=6)
        # 1000 tokens => per-1k equals the whole-run figure.
        self.assertAlmostEqual(
            result["energy_wh_per_1k_tokens"], result["energy_wh"], places=6
        )

    def test_carbon_gate_pass_and_fail(self) -> None:
        ok = evaluate_with_native_energy_stats(
            [50.0], 1.0, tokens=1000, energy_wh_per_1k_tokens_max=1.0
        )
        self.assertEqual(ok["gate"]["verdict"], "pass")
        bad = evaluate_with_native_energy_stats(
            [50.0], 1000.0, tokens=1, energy_wh_per_1k_tokens_max=0.001
        )
        self.assertEqual(bad["gate"]["verdict"], "fail")

    def test_malformed_input_returns_error(self) -> None:
        completed = subprocess.run(
            [str(CLI_PATH)], input="tokens=5\n", text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("error", completed.stderr)


if __name__ == "__main__":
    unittest.main()
