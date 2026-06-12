from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.load_test import run_llm_load_test  # noqa: E402


class LoadTestTests(unittest.TestCase):
    def test_run_llm_load_test_writes_concurrency_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "load.json"
            report = run_llm_load_test(
                prompt="Explain why MLOps is the core of TryOps in five bullet points.",
                concurrency=2,
                requests=5,
                output_path=output,
            )

            self.assertTrue(output.exists())
            self.assertEqual(report["requests"], 5)
            self.assertEqual(report["concurrency"], 2)
            self.assertGreater(report["summary"]["requests_per_second"], 0)
            self.assertGreater(report["summary"]["output_tokens_per_second"], 0)
            self.assertEqual(len(report["records"]), 5)


if __name__ == "__main__":
    unittest.main()
