from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_benchmark import run_llm_benchmark  # noqa: E402


class LlmBenchmarkPipelineTests(unittest.TestCase):
    def test_run_llm_benchmark_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "benchmark.json"
            report = run_llm_benchmark(
                prompt_set_path=ROOT / "samples/eval/golden_prompts.json",
                output_path=output,
            )

            self.assertTrue(output.exists())
            self.assertEqual(report["schema_version"], "tryops.llm_benchmark.v1")
            self.assertEqual(len(report["records"]), 3)
            self.assertIn("run_context", report)
            self.assertIn("trace_id", report["run_context"])
            self.assertGreaterEqual(report["summary"]["quality_score"], 1.0)
            self.assertGreater(report["summary"]["tokens_per_second"], 0)
            self.assertGreater(report["summary"]["latency_p95_ms"], 0)
            self.assertGreaterEqual(report["summary"]["memory_gb"], 0)
            self.assertTrue(report["summary"]["phase_timing"]["available"])
            self.assertGreater(report["summary"]["phase_timing"]["decode_p95_ms"], 0)
            for record in report["records"]:
                self.assertIn("quality_checks", record)
                self.assertIn("cost_usd", record)
                self.assertIn("safety", record)
                self.assertIn("phase_timing", record)


if __name__ == "__main__":
    unittest.main()
