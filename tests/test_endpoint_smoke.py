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

from tryops.endpoint_smoke import run_endpoint_smoke  # noqa: E402


class EndpointSmokeTests(unittest.TestCase):
    def test_endpoint_smoke_exercises_vton_llm_ready_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = run_endpoint_smoke(output_dir=Path(temp_dir))

            self.assertTrue(report["passed"])
            self.assertEqual(report["schema_version"], "tryops.endpoint_smoke.v1")
            checks = {check["name"]: check for check in report["checks"]}
            self.assertTrue(checks["ready"]["passed"])
            self.assertTrue(checks["llm_generate"]["passed"])
            self.assertTrue(checks["vton_infer"]["passed"])
            self.assertTrue(checks["metrics"]["passed"])
            self.assertTrue(checks["metrics"]["contains_llm_counter"])
            self.assertTrue(checks["metrics"]["contains_vton_counter"])
            self.assertTrue(Path(report["artifacts"]["vton_output"]).exists())

    def test_endpoint_smoke_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_endpoint_smoke(output_dir=root)
            report_path = root / "deployed_endpoint_smoke.json"

            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])


if __name__ == "__main__":
    unittest.main()
