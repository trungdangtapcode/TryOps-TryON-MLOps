from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_baseline import estimate_tokens  # noqa: E402
from tryops.pipelines.llm_sensitivity import (  # noqa: E402
    build_prompt_for_target_tokens,
    run_llm_sensitivity_benchmark,
)


class LlmSensitivityTests(unittest.TestCase):
    def test_build_prompt_for_target_tokens_preserves_target_and_class_terms(self) -> None:
        prompt = build_prompt_for_target_tokens(32)

        self.assertEqual(estimate_tokens(prompt), 32)
        self.assertIn("MLOps", prompt)
        self.assertIn("TryOps", prompt)

    def test_run_llm_sensitivity_benchmark_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sensitivity.json"

            report = run_llm_sensitivity_benchmark(
                output_path=output,
                prompt_length_targets=[16, 32],
                output_token_limits=[8, 64],
            )

            self.assertTrue(output.exists())
            self.assertEqual(report["schema_version"], "tryops.llm_sensitivity.v1")
            self.assertEqual(len(report["prompt_length_sensitivity"]), 2)
            self.assertEqual(len(report["output_length_sensitivity"]), 2)
            self.assertIn("run_context", report)
            self.assertIn("prompt_length", report["summary"])
            self.assertIn("output_length", report["summary"])
            self.assertEqual(report["prompt_length_sensitivity"][0]["safety_status"], "passed")
            self.assertTrue(report["output_length_sensitivity"][0]["output_truncated"])
            self.assertFalse(report["output_length_sensitivity"][-1]["output_truncated"])
            self.assertGreaterEqual(report["summary"]["output_length"]["truncated_cases"], 1)

    def test_run_llm_sensitivity_benchmark_rejects_bad_lengths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                run_llm_sensitivity_benchmark(
                    output_path=Path(temp_dir) / "bad.json",
                    prompt_length_targets=[0],
                )


if __name__ == "__main__":
    unittest.main()
