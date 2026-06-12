from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.evaluation import (  # noqa: E402
    bootstrap_ci,
    cohens_kappa,
    concept_coverage_score,
    paired_significance,
)
from tryops.llm_judge import prompt_fingerprint, score_answer  # noqa: E402


class ConceptCoverageTests(unittest.TestCase):
    def test_paraphrase_gets_partial_credit(self) -> None:
        # Exact-phrase matching would score 0; concept coverage gives partial credit.
        score = concept_coverage_score(
            "Quantization reduces memory footprint substantially.",
            ["mentions memory reduction"],
        )["score"]
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_full_coverage_scores_one(self) -> None:
        score = concept_coverage_score(
            "governance registry monitoring reproducibility",
            ["governance registry", "monitoring reproducibility"],
        )["score"]
        self.assertAlmostEqual(score, 1.0, places=6)

    def test_empty_expected_is_perfect(self) -> None:
        self.assertEqual(concept_coverage_score("anything", [])["score"], 1.0)


class BootstrapTests(unittest.TestCase):
    def test_ci_is_deterministic_and_brackets_point(self) -> None:
        vals = [0.2, 0.4, 0.6, 0.8, 1.0]
        a = bootstrap_ci(vals, seed=1)
        b = bootstrap_ci(vals, seed=1)
        self.assertEqual(a, b)  # seeded → reproducible
        self.assertLessEqual(a["ci_lo"], a["point"])
        self.assertLessEqual(a["point"], a["ci_hi"])

    def test_single_value_collapses(self) -> None:
        ci = bootstrap_ci([0.5])
        self.assertEqual(ci["ci_lo"], 0.5)
        self.assertEqual(ci["ci_hi"], 0.5)

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            bootstrap_ci([])


class SignificanceTests(unittest.TestCase):
    def test_clear_difference_is_significant(self) -> None:
        a = [0.9, 0.95, 0.92, 0.88, 0.9]
        b = [0.2, 0.25, 0.18, 0.22, 0.2]
        res = paired_significance(a, b, seed=2)
        self.assertTrue(res["significant"])
        self.assertGreater(res["mean_diff"], 0)

    def test_no_difference_not_significant(self) -> None:
        a = [0.5, 0.5, 0.5, 0.5]
        res = paired_significance(a, a, seed=2)
        self.assertFalse(res["significant"])

    def test_length_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError):
            paired_significance([0.1], [0.1, 0.2])


class KappaTests(unittest.TestCase):
    def test_perfect_agreement(self) -> None:
        self.assertEqual(cohens_kappa(["pass", "fail", "pass"], ["pass", "fail", "pass"]), 1.0)

    def test_disagreement_below_one(self) -> None:
        k = cohens_kappa(["pass", "pass", "fail", "fail"], ["pass", "fail", "pass", "fail"])
        self.assertLess(k, 1.0)


class JudgeTests(unittest.TestCase):
    def test_offline_judge_shape_and_fingerprint_stable(self) -> None:
        v = score_answer("What is MLOps?", "MLOps governs models in production.", ["mentions governance"])
        self.assertIn("score", v)
        self.assertIn(v["source"], {"offline-rubric", "offline-rubric-fallback", "claude-judge"})
        fp1 = prompt_fingerprint("p", "a", ["c"])
        fp2 = prompt_fingerprint("p", "a", ["c"])
        self.assertEqual(fp1, fp2)


if __name__ == "__main__":
    unittest.main()
