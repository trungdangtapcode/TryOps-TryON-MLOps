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

from tryops.deployment import build_deployment_package, rollback_release  # noqa: E402
from tryops.pipelines.promotion import run_local_promotion_pipeline  # noqa: E402


class DeploymentTests(unittest.TestCase):
    def test_build_deployment_package_writes_manifest_release_notes_and_rollback_plan(self) -> None:
        candidate = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        manifest = json.loads((ROOT / "samples/data/demo_manifest.json").read_text())
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            promotion = run_local_promotion_pipeline(
                candidate_payload=candidate,
                dataset_manifest=manifest,
                target_stage="champion",
                output_dir=root / "reports",
            )
            package = build_deployment_package(
                promotion_run_dir=promotion["run_dir"],
                output_dir=root / "deployments",
                profile="production-demo",
                previous_candidate_id="previous-model",
            )
            package_dir = Path(package["package_dir"])

            self.assertTrue((package_dir / "deployment_manifest.json").exists())
            self.assertTrue((package_dir / "release_notes.md").exists())
            self.assertTrue((package_dir / "rollback_plan.json").exists())
            self.assertTrue((package_dir / "gitops" / "application.yaml").exists())
            self.assertTrue((package_dir / "gitops" / "rollout.yaml").exists())
            self.assertTrue((package_dir / "gitops" / "services.yaml").exists())
            self.assertTrue((package_dir / "gitops" / "gitops_validation.json").exists())
            self.assertTrue((Path(promotion["run_dir"]) / "openlineage_run_event.json").exists())
            self.assertTrue((Path(promotion["run_dir"]) / "openlineage_validation.json").exists())
            self.assertEqual(package["manifest"]["profile"], "production-demo")
            self.assertTrue(package["manifest"]["checks"]["promotion_approved"])
            self.assertTrue(package["manifest"]["checks"]["openlineage_event_present"])
            self.assertTrue(package["manifest"]["checks"]["openlineage_validation_passed"])
            self.assertTrue(package["manifest"]["checks"]["gitops_manifests_present"])
            self.assertTrue(package["manifest"]["checks"]["gitops_validation_passed"])
            self.assertEqual(package["rollback_plan"]["previous_candidate_id"], "previous-model")

    def test_rollback_release_writes_record_and_state(self) -> None:
        candidate = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        manifest = json.loads((ROOT / "samples/data/demo_manifest.json").read_text())
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            promotion = run_local_promotion_pipeline(
                candidate_payload=candidate,
                dataset_manifest=manifest,
                target_stage="champion",
                output_dir=root / "reports",
            )
            package = build_deployment_package(
                promotion_run_dir=promotion["run_dir"],
                output_dir=root / "deployments",
                profile="staging",
                previous_candidate_id="previous-model",
            )
            record = rollback_release(
                package_id=package["manifest"]["package_id"],
                packages_dir=root / "deployments",
                reason="unit rollback drill",
            )

            self.assertEqual(record["status"], "recorded")
            self.assertTrue((Path(package["package_dir"]) / "rollback_record.json").exists())
            self.assertTrue((root / "deployments" / "rollback_state.json").exists())


if __name__ == "__main__":
    unittest.main()
