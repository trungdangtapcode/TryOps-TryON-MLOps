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

from tryops.supply_chain import (  # noqa: E402
    audit_dataset_licenses,
    audit_model_sources,
    build_dependency_lock,
    build_spdx_sbom,
    load_dataset_licenses,
    load_model_sources,
    render_requirements_lock,
    write_supply_chain_report,
)


class SupplyChainTests(unittest.TestCase):
    def test_dependency_lock_pins_direct_project_requirements(self) -> None:
        lock = build_dependency_lock(ROOT / "pyproject.toml")
        rendered = render_requirements_lock(lock)

        self.assertTrue(lock["audit"]["passed"])
        self.assertIn("fastapi==", rendered)
        self.assertIn("dvc[s3]==", rendered)
        for line in rendered.splitlines():
            if line and not line.startswith("#"):
                self.assertIn("==", line)

    def test_model_and_dataset_license_audits_pass(self) -> None:
        model_sources = load_model_sources(ROOT / "configs/model_sources.json")
        dataset_licenses = load_dataset_licenses(ROOT / "configs/dataset_licenses.json")

        model_audit = audit_model_sources(model_sources)
        dataset_audit = audit_dataset_licenses(dataset_licenses)

        self.assertTrue(model_audit["passed"])
        self.assertIn("llm", model_audit["workloads"])
        self.assertTrue(dataset_audit["passed"])
        self.assertIn("dress-code", dataset_audit["datasets_with_commercial_restrictions"])

    def test_spdx_sbom_contains_dependencies_models_and_datasets(self) -> None:
        lock = build_dependency_lock(ROOT / "pyproject.toml")
        model_sources = load_model_sources(ROOT / "configs/model_sources.json")
        dataset_licenses = load_dataset_licenses(ROOT / "configs/dataset_licenses.json")

        sbom = build_spdx_sbom(lock=lock, model_sources=model_sources, dataset_licenses=dataset_licenses)
        package_names = {package["name"] for package in sbom["packages"]}

        self.assertEqual(sbom["spdxVersion"], "SPDX-2.3")
        self.assertIn("fastapi", package_names)
        self.assertIn("smollm2-135m-instruct", package_names)
        self.assertIn("dress-code", package_names)

    def test_supply_chain_report_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = write_supply_chain_report(
                pyproject_path=ROOT / "pyproject.toml",
                model_sources_path=ROOT / "configs/model_sources.json",
                dataset_licenses_path=ROOT / "configs/dataset_licenses.json",
                requirements_output=root / "requirements.lock",
                dependency_lock_output=root / "dependency_lock.json",
                sbom_output=root / "sbom.spdx.json",
                output_path=root / "supply_chain_report.json",
            )

            self.assertTrue(report["passed"])
            self.assertTrue((root / "requirements.lock").exists())
            self.assertTrue((root / "sbom.spdx.json").exists())
            persisted = json.loads((root / "supply_chain_report.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["schema_version"], "tryops.supply_chain_report.v1")


if __name__ == "__main__":
    unittest.main()
