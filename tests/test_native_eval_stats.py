from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_eval_stats import bootstrap_ci_native, bootstrap_ci_preferred  # noqa: E402

CLI_PATH = ROOT / "artifacts" / "native" / "tryops_eval_stats_cli"


class NativeEvalStatsBridgeTests(unittest.TestCase):
    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            bootstrap_ci_native([])

    def test_missing_cli_returns_none(self) -> None:
        self.assertIsNone(
            bootstrap_ci_native([1.0, 2.0], cli_path=ROOT / "artifacts" / "native" / "nope")
        )

    def test_preferred_always_returns_a_ci(self) -> None:
        ci = bootstrap_ci_preferred([0.2, 0.4, 0.6, 0.8, 1.0])
        self.assertLessEqual(ci["ci_lo"], ci["point"])
        self.assertLessEqual(ci["point"], ci["ci_hi"])
        self.assertIn(ci["engine"], {"native", "python-fallback"})


@unittest.skipUnless(CLI_PATH.exists(), "native eval stats CLI not built")
class NativeEvalStatsEngineTests(unittest.TestCase):
    def test_ci_brackets_point_and_is_deterministic(self) -> None:
        vals = [0.2, 0.4, 0.6, 0.8, 1.0]
        a = bootstrap_ci_native(vals, seed=7)
        b = bootstrap_ci_native(vals, seed=7)
        self.assertEqual(a["point"], b["point"])
        self.assertEqual((a["ci_lo"], a["ci_hi"]), (b["ci_lo"], b["ci_hi"]))  # deterministic
        self.assertLessEqual(a["ci_lo"], a["point"])
        self.assertLessEqual(a["point"], a["ci_hi"])
        self.assertEqual(a["engine"], "native")

    def test_single_value_collapses(self) -> None:
        ci = bootstrap_ci_native([0.5])
        self.assertEqual(ci["ci_lo"], 0.5)
        self.assertEqual(ci["ci_hi"], 0.5)

    def test_malformed_input_errors(self) -> None:
        completed = subprocess.run(
            [str(CLI_PATH)], input="seed=1\n", text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 2)


if __name__ == "__main__":
    unittest.main()
