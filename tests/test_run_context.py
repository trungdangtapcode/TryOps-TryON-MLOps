from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.run_context import build_run_context, detect_code_version  # noqa: E402


class RunContextTests(unittest.TestCase):
    def test_run_context_contains_ids_code_environment_and_hardware(self) -> None:
        context = build_run_context(run_name="unit-test", run_id="run-fixed", trace_id="trace-fixed")

        self.assertEqual(context["run_id"], "run-fixed")
        self.assertEqual(context["trace_id"], "trace-fixed")
        self.assertIn("version", context["code"])
        self.assertIn("python_version", context["environment"])
        self.assertIn("cpu_count", context["hardware"])

    def test_code_version_prefers_explicit_environment_value(self) -> None:
        old = os.environ.get("TRYOPS_CODE_VERSION")
        os.environ["TRYOPS_CODE_VERSION"] = "sha-test"
        try:
            code = detect_code_version()
        finally:
            if old is None:
                os.environ.pop("TRYOPS_CODE_VERSION", None)
            else:
                os.environ["TRYOPS_CODE_VERSION"] = old

        self.assertEqual(code["version"], "sha-test")
        self.assertEqual(code["source"], "environment")


if __name__ == "__main__":
    unittest.main()
