from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops import db  # noqa: E402
from tryops.runtime_artifacts import account_object_key, artifact_id_from_ref, artifact_uri  # noqa: E402


class RuntimeArtifactTests(unittest.TestCase):
    def test_artifact_object_round_trip_and_uri_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {db.POSTGRES_DSN_ENV: "", db.POSTGRES_DSN_FILE_ENV: ""},
            ):
                conn = db.connect(Path(temp_dir) / "tryops.db")
                try:
                    artifact_id = db.insert_artifact_object(
                        conn,
                        {
                            "account_id": "acct_test",
                            "request_id": "req-test",
                            "role": "vton_output",
                            "backend": "minio",
                            "bucket": "tryops-artifacts",
                            "object_key": account_object_key(
                                "acct_test",
                                "requests",
                                "req-test",
                                "output.png",
                            ),
                            "legacy_path": "artifacts/runtime/vton/accounts/acct_test/req-test.png",
                            "content_type": "image/png",
                            "size_bytes": 123,
                            "sha256": "abc123",
                            "width": 16,
                            "height": 16,
                        },
                    )
                    loaded = db.get_artifact_object(conn, artifact_id)
                finally:
                    conn.close()

        self.assertEqual(artifact_id_from_ref(artifact_uri(artifact_id)), artifact_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["backend"], "minio")
        self.assertEqual(loaded["account_id"], "acct_test")


if __name__ == "__main__":
    unittest.main()
