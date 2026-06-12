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

from tryops.governance import (  # noqa: E402
    REQUIRED_NIST_FUNCTIONS,
    REQUIRED_OWASP_2025_IDS,
    build_governance_report,
    load_governance_controls,
    write_governance_report,
)


class GovernanceTests(unittest.TestCase):
    def test_governance_controls_cover_nist_and_owasp(self) -> None:
        controls = load_governance_controls(ROOT / "configs/governance_risk_controls.json")
        security_cases = json.loads((ROOT / "samples/security/llm_security_cases.json").read_text(encoding="utf-8"))

        report = build_governance_report(controls=controls, llm_security_cases=security_cases)

        self.assertTrue(report["passed"])
        self.assertEqual(set(report["mapping_checks"]["nist"]["covered_functions"]), REQUIRED_NIST_FUNCTIONS)
        self.assertEqual(set(report["mapping_checks"]["owasp_llm_top10_2025"]["covered_ids"]), REQUIRED_OWASP_2025_IDS)
        self.assertGreaterEqual(report["mapping_checks"]["responsible_ai"]["limitation_count"], 3)

    def test_governance_report_writes_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "governance_report.json"

            report = write_governance_report(
                controls_path=ROOT / "configs/governance_risk_controls.json",
                output_path=output,
                llm_security_cases_path=ROOT / "samples/security/llm_security_cases.json",
            )

            self.assertTrue(output.exists())
            self.assertTrue(report["passed"])
            persisted = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(persisted["schema_version"], "tryops.governance_report.v1")

    def test_governance_report_fails_when_owasp_mapping_is_missing(self) -> None:
        controls = load_governance_controls(ROOT / "configs/governance_risk_controls.json")
        controls["owasp_llm_top10_2025"] = controls["owasp_llm_top10_2025"][:-1]

        report = build_governance_report(controls=controls)

        self.assertFalse(report["passed"])
        self.assertIn("LLM10:2025", report["mapping_checks"]["owasp_llm_top10_2025"]["missing_ids"])


if __name__ == "__main__":
    unittest.main()
