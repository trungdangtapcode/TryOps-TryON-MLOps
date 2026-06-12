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

from tryops.pipelines.promotion import run_local_promotion_pipeline


class PromotionPipelineTests(unittest.TestCase):
    def test_pipeline_writes_evidence_artifacts(self) -> None:
        candidate = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        manifest = json.loads((ROOT / "samples/data/demo_manifest.json").read_text())
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_local_promotion_pipeline(
                candidate_payload=candidate,
                dataset_manifest=manifest,
                target_stage="champion",
                output_dir=Path(temp_dir),
            )
            run_dir = Path(result["run_dir"])
            self.assertTrue(result["approved"])
            self.assertTrue(result["data_validation_passed"])
            self.assertTrue((run_dir / "promotion_decision.json").exists())
            self.assertTrue((run_dir / "data_validation.json").exists())
            self.assertTrue((run_dir / "lineage.json").exists())
            self.assertTrue((run_dir / "native_policy_decision.json").exists())
            self.assertTrue((run_dir / "run_context.json").exists())
            self.assertTrue((run_dir / "registry_entry.json").exists())
            self.assertTrue((run_dir / "model_card.md").exists())
            self.assertTrue((run_dir / "data_card.md").exists())
            self.assertEqual(result["run_id"], candidate["metadata"]["pipeline_run_id"])
            self.assertTrue(result["trace_id"].startswith("trace-promotion-"))

            run_context = json.loads((run_dir / "run_context.json").read_text())
            native_policy = json.loads((run_dir / "native_policy_decision.json").read_text())
            registry_entry = json.loads((run_dir / "registry_entry.json").read_text())
            self.assertEqual(registry_entry["alias"], "champion")
            self.assertIn("available", native_policy)
            self.assertIn("code", run_context)
            self.assertIn("environment", run_context)
            self.assertIn("hardware", run_context)


if __name__ == "__main__":
    unittest.main()
