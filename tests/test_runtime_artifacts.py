from __future__ import annotations

import os
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops import db  # noqa: E402
from tryops.api import _persist_vton_request_input_artifacts  # noqa: E402
from tryops.runtime_artifacts import account_object_key, artifact_id_from_ref, artifact_uri  # noqa: E402
from tryops.simple_image import solid_rgb, write_png_rgb  # noqa: E402


class FakeArtifactStorage:
    bucket = "tryops-artifacts"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_file(self, *, object_key: str, path: str | Path, content_type: str) -> dict[str, object]:
        data = Path(path).read_bytes()
        self.objects[object_key] = data
        return {
            "backend": "minio",
            "bucket": self.bucket,
            "object_key": object_key,
            "content_type": content_type,
            "size_bytes": len(data),
            "sha256": sha256(data).hexdigest(),
        }


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

    def test_vton_request_input_snapshots_are_persisted_under_request_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person = root / "person.png"
            garment = root / "garment.png"
            write_png_rgb(person, solid_rgb(8, 8, (10, 20, 30)))
            write_png_rgb(garment, solid_rgb(8, 8, (200, 20, 30)))
            conn = db.connect(root / "tryops.db")
            storage = FakeArtifactStorage()
            report = {
                "inputs": {
                    "person": {"checksum": "sha256:person"},
                    "garment": {"checksum": "sha256:garment"},
                }
            }
            try:
                _persist_vton_request_input_artifacts(
                    conn=conn,
                    storage=storage,
                    report=report,
                    clean={
                        "person_image_path": str(person),
                        "garment_image_path": str(garment),
                    },
                    account_id="acct_test",
                    request_id="req-test",
                )
                person_id = artifact_id_from_ref(report["inputs"]["person"]["path"])
                garment_id = artifact_id_from_ref(report["inputs"]["garment"]["path"])
                person_record = db.get_artifact_object(conn, person_id or "")
                garment_record = db.get_artifact_object(conn, garment_id or "")
            finally:
                conn.close()

        self.assertEqual(
            report["inputs"]["person"]["storage"]["object_key"],
            "runtime/vton/accounts/acct_test/requests/req-test/person.png",
        )
        self.assertEqual(
            report["inputs"]["garment"]["storage"]["object_key"],
            "runtime/vton/accounts/acct_test/requests/req-test/garment.png",
        )
        self.assertIn("runtime/vton/accounts/acct_test/requests/req-test/person.png", storage.objects)
        self.assertIn("runtime/vton/accounts/acct_test/requests/req-test/garment.png", storage.objects)
        self.assertEqual(person_record["role"], "vton_person_input")
        self.assertEqual(garment_record["role"], "vton_garment_input")


if __name__ == "__main__":
    unittest.main()
