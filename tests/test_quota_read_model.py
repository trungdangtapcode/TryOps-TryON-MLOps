from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.quota_read_model import build_quota_read_model, load_quota_read_model  # noqa: E402


class QuotaReadModelTests(unittest.TestCase):
    def test_build_read_model_from_native_snapshot(self) -> None:
        report = build_quota_read_model(
            snapshot={
                "schema_version": "tryops.quota_snapshot.v1",
                "engine": "native_rust_gateway",
                "usage": [
                    {
                        "period": "2026-06-12",
                        "user_hash": "tenant-hash",
                        "dimension": "llm_tokens_per_day",
                        "used": 300,
                    }
                ],
            }
        )

        self.assertEqual(report["schema_version"], "tryops.native_quota_read_model.v1")
        self.assertTrue(report["passed"])
        self.assertTrue(report["summary"]["native_source"])
        self.assertEqual(report["tenants"][0]["user_hash"], "tenant-hash")
        self.assertNotIn("user_id", json.dumps(report))

    def test_load_prefers_native_go_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "native_quota_read_model.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "tryops.native_quota_read_model.v1",
                        "passed": True,
                        "summary": {"tenants": 1},
                    }
                ),
                encoding="utf-8",
            )
            old = os.environ.get("TRYOPS_QUOTA_READ_MODEL_PATH")
            os.environ["TRYOPS_QUOTA_READ_MODEL_PATH"] = str(path)
            try:
                report = load_quota_read_model()
            finally:
                if old is None:
                    os.environ.pop("TRYOPS_QUOTA_READ_MODEL_PATH", None)
                else:
                    os.environ["TRYOPS_QUOTA_READ_MODEL_PATH"] = old

        self.assertEqual(report["source"], "native_go_artifact")
        self.assertEqual(report["summary"]["tenants"], 1)


if __name__ == "__main__":
    unittest.main()
