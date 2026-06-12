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

from tryops.config import load_json_config, require_keys
from tryops.contracts import ModelCandidate
from tryops.policy import evaluate_promotion
from tryops.registry import build_registry_entry


class ConfigAndRegistryTests(unittest.TestCase):
    def test_load_project_config(self) -> None:
        payload = load_json_config(ROOT / "configs/project.json")
        require_keys(payload, ["project_name", "theme", "workloads", "registry"])
        self.assertEqual(payload["project_name"], "TryOps")

    def test_require_keys_reports_missing(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required config keys"):
            require_keys({"present": True}, ["present", "missing"])

    def test_load_json_config_rejects_non_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text(json.dumps(["not", "object"]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must contain a JSON object"):
                load_json_config(path)

    def test_registry_entry_for_approved_champion(self) -> None:
        payload = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        candidate = ModelCandidate.from_dict(payload)
        decision = evaluate_promotion(candidate, target_stage="champion")
        entry = build_registry_entry(candidate, decision, alias="champion")
        self.assertEqual(entry.alias, "champion")
        self.assertEqual(entry.tags["decision"], "approved")
        self.assertEqual(entry.tags["dataset_version"], "vitonhd-demo-v1")

    def test_rejected_candidate_cannot_be_champion(self) -> None:
        payload = json.loads((ROOT / "samples/candidates/vton_candidate_bad.json").read_text())
        candidate = ModelCandidate.from_dict(payload)
        decision = evaluate_promotion(candidate, target_stage="champion")
        with self.assertRaisesRegex(ValueError, "cannot assign champion"):
            build_registry_entry(candidate, decision, alias="champion")


if __name__ == "__main__":
    unittest.main()

