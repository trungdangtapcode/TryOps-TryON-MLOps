from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_experiment_stats import analyze_with_native_experiment_stats  # noqa: E402


class ExperimentStatsTests(unittest.TestCase):
    def test_python_fallback_reports_uplift_and_early_stop(self) -> None:
        stats = analyze_with_native_experiment_stats(
            holdback={"name": "champion_holdback", "impressions": 1000.0, "rewards": 820.0},
            variants=[
                {"name": "champion", "impressions": 950.0, "rewards": 786.0},
                {"name": "challenger", "impressions": 800.0, "rewards": 760.0},
            ],
            experiment_id="exp",
            min_detectable_effect=0.05,
            cli_path=ROOT / "artifacts" / "native" / "missing-experiment-stats",
        )
        challenger = _variant(stats, "challenger")
        champion = _variant(stats, "champion")

        self.assertFalse(stats["available"])
        self.assertEqual(stats["best_variant"], "challenger")
        self.assertGreater(challenger["uplift_absolute"], champion["uplift_absolute"])
        self.assertTrue(challenger["uplift_ci"]["excludes_zero"])
        self.assertTrue(challenger["sequential"]["early_stop"])
        self.assertEqual(challenger["sequential"]["verdict"], "accept_variant")

    def test_minimum_sample_keeps_sequential_test_open(self) -> None:
        stats = analyze_with_native_experiment_stats(
            holdback={"name": "holdback", "impressions": 20.0, "rewards": 16.0},
            variants=[{"name": "challenger", "impressions": 20.0, "rewards": 20.0}],
            min_sample_size=100.0,
            cli_path=ROOT / "artifacts" / "native" / "missing-experiment-stats",
        )
        challenger = _variant(stats, "challenger")

        self.assertFalse(challenger["sequential"]["early_stop"])
        self.assertEqual(challenger["sequential"]["reason"], "minimum_sample_not_met")


def _variant(stats: dict[str, object], name: str) -> dict[str, object]:
    for variant in stats["variants"]:  # type: ignore[index]
        if variant["name"] == name:
            return variant
    raise KeyError(name)


if __name__ == "__main__":
    unittest.main()
