from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_perf_stats import evaluate_with_native_perf_stats  # noqa: E402
from tryops.pipelines.llm_benchmark import _percentile  # noqa: E402

CLI_PATH = ROOT / "artifacts" / "native" / "tryops_perf_stats_cli"


class NativePerfStatsBridgeTests(unittest.TestCase):
    def test_empty_latency_raises(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_with_native_perf_stats([])

    def test_missing_cli_degrades_gracefully(self) -> None:
        result = evaluate_with_native_perf_stats(
            [1.0, 2.0, 3.0], cli_path=ROOT / "artifacts" / "native" / "does_not_exist"
        )
        self.assertFalse(result["available"])
        self.assertIn("not found", result["reason"])


@unittest.skipUnless(CLI_PATH.exists(), "native perf stats CLI not built")
class NativePerfStatsEngineTests(unittest.TestCase):
    def test_percentiles_match_python_reference(self) -> None:
        latency = [300.1, 12.5, 7556.3, 42.0, 9.9]
        result = evaluate_with_native_perf_stats(latency, [18.5, 12.0, 20.1, 15.0, 11.0])
        self.assertTrue(result["available"])
        self.assertEqual(result["count"], len(latency))
        for quantile, key in [(0.50, "p50"), (0.95, "p95"), (0.99, "p99")]:
            self.assertAlmostEqual(
                result["latency_ms"][key], _percentile(latency, quantile), places=4
            )

    def test_slo_pass_and_fail(self) -> None:
        latency = [10.0, 20.0, 30.0]
        throughput = [50.0, 60.0, 70.0]
        ok = evaluate_with_native_perf_stats(
            latency, throughput, latency_p95_ms_max=100.0, tokens_per_second_min=10.0
        )
        self.assertEqual(ok["slo"]["verdict"], "pass")
        self.assertTrue(ok["slo"]["latency_pass"])
        self.assertTrue(ok["slo"]["throughput_pass"])

        bad = evaluate_with_native_perf_stats(
            latency, throughput, latency_p95_ms_max=5.0, tokens_per_second_min=1000.0
        )
        self.assertEqual(bad["slo"]["verdict"], "fail")
        self.assertFalse(bad["slo"]["latency_pass"])
        self.assertFalse(bad["slo"]["throughput_pass"])

    def test_malformed_input_returns_error_payload(self) -> None:
        completed = subprocess.run(
            [str(CLI_PATH)], input="garbage=1\n", text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("error", completed.stderr)


if __name__ == "__main__":
    unittest.main()
