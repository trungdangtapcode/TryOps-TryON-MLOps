from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.model_provenance import build_model_provenance, verify_model_signature_bundle  # noqa: E402
from tryops.native_model_scan import write_minimal_safetensors  # noqa: E402


class ModelProvenanceTests(unittest.TestCase):
    def test_build_model_provenance_writes_statement_bundle_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_path = write_minimal_safetensors(root / "model.safetensors")
            provenance = build_model_provenance(
                candidate_id="candidate-001",
                workload="llm",
                model_name="demo",
                model_version="1",
                model_artifact_paths=[model_path],
                evidence_uris={"model_artifact_scan": str(root / "scan.json")},
                output_dir=root / "out",
                pipeline_run_id="run-001",
                verifier_cli_path=root / "missing-native-provenance-cli",
            )

            self.assertEqual(provenance["schema_version"], "tryops.model_provenance.v1")
            self.assertTrue(provenance["passed"])
            self.assertTrue((root / "out" / "model_provenance.intoto.json").exists())
            self.assertTrue((root / "out" / "model_signature_bundle.json").exists())

    def test_verify_model_signature_bundle_detects_tampered_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_path = write_minimal_safetensors(root / "model.safetensors")
            provenance = build_model_provenance(
                candidate_id="candidate-001",
                workload="llm",
                model_name="demo",
                model_version="1",
                model_artifact_paths=[model_path],
                evidence_uris={},
                output_dir=root / "out",
                pipeline_run_id="run-001",
                verifier_cli_path=root / "missing-native-provenance-cli",
            )
            model_path.write_bytes(b"tampered")
            verification = verify_model_signature_bundle(
                artifact_path=model_path,
                bundle_path=provenance["signature_bundle_uri"],
                expected_signer_identity="tryops-local-ci",
                cli_path=root / "missing-native-provenance-cli",
            )

            self.assertFalse(verification["passed"])
            self.assertIn("artifact sha256 does not match signed subject", verification["errors"])


if __name__ == "__main__":
    unittest.main()
