from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tryops.gitops import build_gitops_manifests
from tryops.native_gitops import validate_gitops_manifests


class GitOpsTests(unittest.TestCase):
    def test_build_gitops_manifests_outputs_argocd_application_and_rollout(self) -> None:
        manifest = {
            "package_id": "candidate-001-production-demo",
            "profile": "production-demo",
            "candidate_id": "candidate-001",
            "model": {
                "workload": "vton",
                "alias": "champion",
                "name": "catvton-baseline",
                "version": "0.1.0",
            },
            "routing": {"adapter": "naive-overlay-vton"},
        }

        bundle = build_gitops_manifests(deployment_manifest=manifest)

        self.assertEqual(bundle["schema_version"], "tryops.gitops_manifests.v1")
        self.assertEqual(bundle["rollout"]["strategy"], "canary")
        self.assertIn("kind: Application", bundle["files"]["application.yaml"])
        self.assertIn("repoURL:", bundle["files"]["application.yaml"])
        self.assertIn("kind: Rollout", bundle["files"]["rollout.yaml"])
        self.assertIn("stableService:", bundle["files"]["rollout.yaml"])
        self.assertIn("canaryService:", bundle["files"]["rollout.yaml"])
        self.assertIn("setWeight: 10", bundle["files"]["rollout.yaml"])
        self.assertIn("pause:", bundle["files"]["rollout.yaml"])

    def test_native_gitops_validation_accepts_generated_bundle(self) -> None:
        manifest = {
            "package_id": "candidate-001-production-demo",
            "profile": "production-demo",
            "candidate_id": "candidate-001",
            "model": {
                "workload": "vton",
                "alias": "champion",
                "name": "catvton-baseline",
                "version": "0.1.0",
            },
            "routing": {"adapter": "naive-overlay-vton"},
        }
        bundle = build_gitops_manifests(deployment_manifest=manifest)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for filename, content in bundle["files"].items():
                (root / filename).write_text(content, encoding="utf-8")
            validation = validate_gitops_manifests(root, candidate_id="candidate-001")

        self.assertTrue(validation["passed"], validation)
        self.assertEqual(validation["manifest_count"], 4)
        self.assertGreaterEqual(validation["service_count"], 2)


if __name__ == "__main__":
    unittest.main()
