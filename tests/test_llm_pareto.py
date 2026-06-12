from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_pareto import _recommend, pareto_frontier  # noqa: E402


def _variant(name, quality, tps, vram, verdict="pass", available=True):
    return {
        "variant": name,
        "available": available,
        "quality_score": quality,
        "tokens_per_second": tps,
        "peak_vram_gb": vram,
        "slo": {"verdict": verdict},
    }


class ParetoFrontierTests(unittest.TestCase):
    def test_dominated_variant_is_excluded(self) -> None:
        variants = [
            _variant("fp16", 0.50, 20.0, 1.00),
            _variant("8bit", 0.50, 15.0, 0.60),
            _variant("4bit", 0.48, 18.0, 0.35),
            _variant("bad", 0.40, 10.0, 1.50),  # dominated on every axis
        ]
        frontier = {v["variant"] for v in pareto_frontier(variants)}
        self.assertIn("fp16", frontier)
        self.assertIn("4bit", frontier)
        self.assertNotIn("bad", frontier)

    def test_unavailable_variants_ignored(self) -> None:
        variants = [
            _variant("fp16", 0.5, 20.0, 1.0),
            _variant("4bit", 0.0, 0.0, 0.0, available=False),
        ]
        frontier = [v["variant"] for v in pareto_frontier(variants)]
        self.assertEqual(frontier, ["fp16"])

    def test_recommendation_prefers_smallest_vram_within_quality_band(self) -> None:
        variants = [
            _variant("fp16", 0.50, 20.0, 1.00),
            _variant("8bit", 0.50, 15.0, 0.60),
            _variant("4bit", 0.49, 18.0, 0.35),
        ]
        rec = _recommend(variants)
        self.assertEqual(rec["variant"], "4bit")

    def test_recommendation_skips_slo_failing_variant(self) -> None:
        variants = [
            _variant("fp16", 0.50, 20.0, 1.00, verdict="pass"),
            _variant("4bit", 0.50, 18.0, 0.35, verdict="fail"),
        ]
        rec = _recommend(variants)
        self.assertEqual(rec["variant"], "fp16")

    def test_recommendation_handles_no_usable_variants(self) -> None:
        rec = _recommend([_variant("4bit", 0.0, 0.0, 0.0, available=False)])
        self.assertIsNone(rec["variant"])


if __name__ == "__main__":
    unittest.main()
