from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.contracts import ModelCandidate
from tryops.policy import evaluate_promotion


class PolicyTests(unittest.TestCase):
    def test_good_vton_candidate_passes_champion_gate(self) -> None:
        payload = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        decision = evaluate_promotion(ModelCandidate.from_dict(payload), target_stage="champion")
        self.assertTrue(decision.approved)
        self.assertEqual(decision.reasons, ["all promotion gates passed"])

    def test_bad_vton_candidate_fails_with_multiple_reasons(self) -> None:
        payload = json.loads((ROOT / "samples/candidates/vton_candidate_bad.json").read_text())
        decision = evaluate_promotion(ModelCandidate.from_dict(payload), target_stage="champion")
        self.assertFalse(decision.approved)
        joined = " ".join(decision.reasons)
        self.assertIn("missing required artifacts", joined)
        self.assertIn("missing approvals", joined)
        self.assertIn("unaccepted risk status", joined)
        self.assertIn("critical vulnerabilities", joined)
        self.assertIn("candidate artifact is not signed", joined)
        self.assertIn("garment_fidelity", joined)

    def test_llm_candidate_requires_passing_guardrail_report(self) -> None:
        payload = _llm_candidate()
        decision = evaluate_promotion(ModelCandidate.from_dict(payload), target_stage="champion")

        self.assertTrue(decision.approved)

    def test_llm_candidate_fails_on_guardrail_leak_verdict(self) -> None:
        payload = _llm_candidate()
        payload["metadata"]["guardrails"] = {
            "status": "blocked",
            "failed_cases": 1,
            "blocked_risk_ids": ["LLM07:2025"],
        }
        decision = evaluate_promotion(ModelCandidate.from_dict(payload), target_stage="champion")

        self.assertFalse(decision.approved)
        joined = " ".join(decision.reasons)
        self.assertIn("unaccepted guardrail verdict", joined)
        self.assertIn("guardrail failed cases", joined)
        self.assertIn("LLM07:2025", joined)

    def test_llm_candidate_fails_on_missing_model_provenance(self) -> None:
        payload = _llm_candidate()
        del payload["artifacts"]["model_provenance"]
        payload["metadata"]["model_provenance"] = {
            "status": "missing",
            "statement_type": "missing",
            "predicate_type": "missing",
            "signature_mode": "missing",
            "verified": False,
        }
        decision = evaluate_promotion(ModelCandidate.from_dict(payload), target_stage="champion")

        self.assertFalse(decision.approved)
        joined = " ".join(decision.reasons)
        self.assertIn("missing required artifacts", joined)
        self.assertIn("model provenance status", joined)
        self.assertIn("model provenance verification did not pass", joined)

def _llm_candidate() -> dict[str, object]:
    return {
        "candidate_id": "llm-qwen-2026-06-11-001",
        "workload": "llm",
        "model_name": "Qwen2.5-0.5B-Instruct",
        "model_version": "2026-06-11",
        "metrics": {
            "quality_score": 0.91,
            "tokens_per_second": 90.0,
            "latency_p95_ms": 120.0,
            "memory_gb": 1.5,
        },
        "artifacts": {
            "model_card": "reports/generated/llm/model_card.md",
            "data_card": "reports/generated/llm/data_card.md",
            "evaluation_report": "artifacts/eval/llm_baseline/benchmark.json",
            "sbom": "artifacts/eval/supply_chain/sbom.spdx.json",
            "guardrail_report": "artifacts/eval/guardrails/guardrail_report.json",
            "model_artifact_scan": "artifacts/eval/model_supply_chain/safe_model_artifact_scan.json",
            "model_provenance": "artifacts/eval/model_supply_chain/model_provenance.json",
        },
        "approvals": ["mlops_owner", "risk_owner"],
        "risk_status": "low",
        "vulnerabilities": {"critical": 0, "high": 0},
        "signed": True,
        "metadata": {
            "code_version": "local",
            "dataset_version": "golden-prompts-v1",
            "pipeline_run_id": "run-llm-guardrails",
            "guardrails": {
                "status": "passed",
                "failed_cases": 0,
                "blocked_risk_ids": [],
            },
            "model_provenance": {
                "status": "passed",
                "statement_type": "https://in-toto.io/Statement/v1",
                "predicate_type": "https://slsa.dev/provenance/v1",
                "signature_mode": "local-dsse-digest",
                "signer_identity": "tryops-local-ci",
                "verified": True,
            },
            "model_artifacts": {
                "serialization_policy": "safetensors_only",
                "scan_status": "passed",
                "unsafe_file_count": 0,
                "safetensors_files": 1,
                "rejected_extensions": [],
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
