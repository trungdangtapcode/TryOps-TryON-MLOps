from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.eval_leaderboard import run_eval_leaderboard  # noqa: E402


def _benchmark(adapter: str, scores_text: list[tuple[str, str]]) -> dict:
    return {
        "schema_version": "tryops.llm_benchmark.v1",
        "adapter": adapter,
        "records": [
            {"id": f"p{i}", "prompt": "q", "output_text": text,
             "expected_characteristics": [crit]}
            for i, (text, crit) in enumerate(scores_text)
        ],
    }


class EvalLeaderboardTests(unittest.TestCase):
    def test_builds_ranked_board_with_ci_and_kappa(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            good = d / "good.json"
            good.write_text(json.dumps(_benchmark("good", [
                ("governance registry monitoring", "governance registry monitoring"),
                ("reproducibility lineage promotion", "reproducibility lineage promotion"),
            ])), encoding="utf-8")
            poor = d / "poor.json"
            poor.write_text(json.dumps(_benchmark("poor", [
                ("unrelated text here", "governance registry monitoring"),
                ("nothing matches", "reproducibility lineage promotion"),
            ])), encoding="utf-8")
            out = d / "lb.json"
            report = run_eval_leaderboard(
                benchmark_paths=[good, poor], output_path=out
            )
            self.assertEqual(report["schema_version"], "tryops.eval_leaderboard.v1")
            # The clearly-better variant ranks first.
            self.assertEqual(report["ranking"][0], "good")
            top = report["leaderboard"][0]
            self.assertIn("quality_ci", top)
            self.assertIn("judge_rubric_kappa", top)
            self.assertTrue(out.exists())

    def test_significance_between_top_two_same_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = d / "a.json"
            a.write_text(json.dumps(_benchmark("a", [
                ("governance registry monitoring", "governance registry monitoring"),
                ("reproducibility lineage promotion", "reproducibility lineage promotion"),
                ("policy gates evaluation", "policy gates evaluation"),
            ])), encoding="utf-8")
            b = d / "b.json"
            b.write_text(json.dumps(_benchmark("b", [
                ("none", "governance registry monitoring"),
                ("none", "reproducibility lineage promotion"),
                ("none", "policy gates evaluation"),
            ])), encoding="utf-8")
            report = run_eval_leaderboard(benchmark_paths=[a, b], output_path=d / "lb.json")
            sig = report["top_two_significance"]
            self.assertIsNotNone(sig)
            self.assertTrue(sig["significant"])

    def test_missing_benchmark_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            report = run_eval_leaderboard(
                benchmark_paths=[d / "nope.json"], output_path=d / "lb.json"
            )
            self.assertEqual(report["ranking"], [])


if __name__ == "__main__":
    unittest.main()
