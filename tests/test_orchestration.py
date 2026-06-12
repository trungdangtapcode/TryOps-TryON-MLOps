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

from tryops.orchestration import (  # noqa: E402
    build_tryops_pipeline_spec,
    render_kfp_native_manifest,
    validate_pipeline_spec,
    write_orchestration_skeleton,
)


class OrchestrationTests(unittest.TestCase):
    def test_tryops_pipeline_spec_is_acyclic_and_ordered(self) -> None:
        spec = build_tryops_pipeline_spec()

        validation = validate_pipeline_spec(spec)

        self.assertTrue(validation["passed"])
        self.assertEqual(validation["terminal_steps"], ["package-deployment"])
        validate_step = next(step for step in spec["steps"] if step["id"] == "validate-data")
        self.assertIn("scripts/validate_dataset_manifest.py", validate_step["command"])
        self.assertLess(
            validation["topological_order"].index("validate-data"),
            validation["topological_order"].index("evaluate-promotion"),
        )
        self.assertLess(
            validation["topological_order"].index("evaluate-promotion"),
            validation["topological_order"].index("package-deployment"),
        )

    def test_pipeline_validation_rejects_missing_dependency(self) -> None:
        spec = build_tryops_pipeline_spec()
        spec["steps"][0]["dependencies"] = ["missing-step"]

        validation = validate_pipeline_spec(spec)

        self.assertFalse(validation["passed"])
        self.assertEqual(validation["missing_dependencies"][0]["dependency"], "missing-step")

    def test_kfp_manifest_contains_pipeline_resources_and_tasks(self) -> None:
        manifest = render_kfp_native_manifest(build_tryops_pipeline_spec())

        self.assertIn("apiVersion: pipelines.kubeflow.org/v2beta1", manifest)
        self.assertIn("kind: Pipeline", manifest)
        self.assertIn("kind: PipelineVersion", manifest)
        self.assertIn("name: validate-data", manifest)
        self.assertIn("name: evaluate-promotion", manifest)

    def test_write_orchestration_skeleton_creates_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = write_orchestration_skeleton(output_dir=temp_dir)
            root = Path(temp_dir)

            self.assertTrue(report["passed"])
            self.assertTrue((root / "tryops_pipeline_dag.json").exists())
            self.assertTrue((root / "tryops_pipeline.kfp.yaml").exists())
            self.assertTrue((root / "orchestration_report.json").exists())
            persisted = json.loads((root / "orchestration_report.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["schema_version"], "tryops.orchestration_report.v1")


if __name__ == "__main__":
    unittest.main()
