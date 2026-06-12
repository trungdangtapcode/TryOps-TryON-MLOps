from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.data_validation import validate_dataset_manifest


class DataValidationTests(unittest.TestCase):
    def test_manifest_passes_with_required_fields(self) -> None:
        report = validate_dataset_manifest(
            {
                "entries": [
                    {
                        "id": "p001-g001",
                        "path": "data/raw/demo/person001.png",
                        "split": "demo",
                        "checksum": "sha256:a",
                        "license": "public-demo",
                    }
                ]
            }
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["stats"]["entry_count"], 1)

    def test_manifest_fails_on_duplicate_and_bad_split(self) -> None:
        report = validate_dataset_manifest(
            {
                "entries": [
                    {
                        "id": "same",
                        "path": "a.png",
                        "split": "demo",
                        "checksum": "sha256:a",
                        "license": "public-demo",
                    },
                    {
                        "id": "same",
                        "path": "b.png",
                        "split": "invalid",
                        "checksum": "sha256:a",
                        "license": "public-demo",
                    },
                ]
            }
        )
        self.assertFalse(report["passed"])
        errors = " ".join(report["errors"])
        self.assertIn("duplicate id", errors)
        self.assertIn("duplicate checksum", errors)
        self.assertIn("invalid split", errors)


if __name__ == "__main__":
    unittest.main()

