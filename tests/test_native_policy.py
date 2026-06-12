from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.contracts import ModelCandidate  # noqa: E402
from tryops.native_policy import serialize_candidate_for_native  # noqa: E402


class NativePolicyTests(unittest.TestCase):
    def test_serialize_candidate_for_native_wire_format(self) -> None:
        payload = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        candidate = ModelCandidate.from_dict(payload)
        wire = serialize_candidate_for_native(candidate, target_stage="champion")

        self.assertIn("target_stage=champion", wire)
        self.assertIn("candidate_id=vton-catvton-2026-06-11-001", wire)
        self.assertIn("metric.garment_fidelity=0.81", wire)
        self.assertIn("artifact.model_card=", wire)
        self.assertIn("artifact.model_artifact_scan=", wire)
        self.assertIn("artifact.model_provenance=", wire)
        self.assertIn("metadata.model_provenance.predicate_type=https://slsa.dev/provenance/v1", wire)
        self.assertIn("metadata.model_provenance.verified=true", wire)
        self.assertIn("metadata.model_artifacts.serialization_policy=safetensors_only", wire)
        self.assertIn("metadata.model_artifacts.scan_status=passed", wire)
        self.assertIn("approval=mlops_owner", wire)
        self.assertIn("signed=true", wire)


if __name__ == "__main__":
    unittest.main()
