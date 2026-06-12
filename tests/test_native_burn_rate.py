from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_burn_rate import evaluate_with_native_burn_rate  # noqa: E402

CLI_PATH = ROOT / "artifacts" / "native" / "tryops_burn_rate_cli"


class NativeBurnRateBridgeTests(unittest.TestCase):
    def test_empty_windows_raise(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_with_native_burn_rate(slo_name="llm", error_budget_ratio=0.01, windows=[])

    def test_missing_cli_degrades_gracefully(self) -> None:
        result = evaluate_with_native_burn_rate(
            slo_name="llm",
            error_budget_ratio=0.01,
            windows=[
                {
                    "name": "page_fast",
                    "long_bad": 0,
                    "long_total": 10,
                    "short_bad": 0,
                    "short_total": 10,
                    "burn_rate_threshold": 14.4,
                    "severity": "page",
                }
            ],
            cli_path=ROOT / "artifacts" / "native" / "does_not_exist",
        )

        self.assertFalse(result["available"])
        self.assertIn("not found", result["reason"])


@unittest.skipUnless(CLI_PATH.exists(), "native burn-rate CLI not built")
class NativeBurnRateEngineTests(unittest.TestCase):
    def test_ok_and_page_verdicts(self) -> None:
        ok = evaluate_with_native_burn_rate(
            slo_name="llm",
            error_budget_ratio=0.01,
            windows=[
                {
                    "name": "page_fast",
                    "long_bad": 0,
                    "long_total": 100,
                    "short_bad": 0,
                    "short_total": 20,
                    "burn_rate_threshold": 14.4,
                    "severity": "page",
                }
            ],
            cli_path=CLI_PATH,
        )
        self.assertEqual(ok["verdict"], "ok")
        self.assertFalse(ok["windows"][0]["firing"])

        page = evaluate_with_native_burn_rate(
            slo_name="llm",
            error_budget_ratio=0.01,
            windows=[
                {
                    "name": "page_fast",
                    "long_bad": 20,
                    "long_total": 100,
                    "short_bad": 5,
                    "short_total": 20,
                    "burn_rate_threshold": 14.4,
                    "severity": "page",
                }
            ],
            cli_path=CLI_PATH,
        )
        self.assertEqual(page["verdict"], "page")
        self.assertTrue(page["windows"][0]["firing"])
        self.assertAlmostEqual(page["windows"][0]["long"]["burn_rate"], 20.0)

    def test_malformed_payload_returns_error(self) -> None:
        completed = subprocess.run(
            [str(CLI_PATH)], input="garbage=1\n", text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("error", completed.stderr)


if __name__ == "__main__":
    unittest.main()
