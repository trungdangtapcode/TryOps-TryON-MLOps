from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EvalAssetsTests(unittest.TestCase):
    def test_golden_vton_pairs_are_fixed(self) -> None:
        payload = json.loads((ROOT / "samples/eval/golden_vton_pairs.json").read_text())
        self.assertEqual(payload["set_id"], "tryops-vton-golden-pairs-v1")
        self.assertGreaterEqual(len(payload["pairs"]), 1)
        for pair in payload["pairs"]:
            self.assertIn("person_image_uri", pair)
            self.assertIn("garment_image_uri", pair)
            self.assertIn("expected_checks", pair)

    def test_vton_failure_taxonomy_has_required_labels(self) -> None:
        payload = json.loads((ROOT / "samples/eval/vton_failure_taxonomy.json").read_text())
        labels = {item["id"] for item in payload["labels"]}
        self.assertIn("texture_loss", labels)
        self.assertIn("sleeve_distortion", labels)
        self.assertIn("identity_shift", labels)
        self.assertIn("occlusion_failure", labels)

    def test_golden_prompts_have_expected_characteristics(self) -> None:
        payload = json.loads((ROOT / "samples/eval/golden_prompts.json").read_text())
        self.assertGreaterEqual(len(payload["prompts"]), 3)
        for item in payload["prompts"]:
            self.assertIn("expected_characteristics", item)
            self.assertTrue(item["expected_characteristics"])


if __name__ == "__main__":
    unittest.main()

