from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.api import create_app  # noqa: E402
from tryops.simple_image import RgbImage, solid_rgb, write_png_rgb  # noqa: E402
from tryops.vton_native_bridge import quality_score_from_native_metrics  # noqa: E402


class VTONNativeBridgeTests(unittest.TestCase):
    def test_quality_score_from_native_metrics_clamps_similarity(self) -> None:
        self.assertEqual(
            quality_score_from_native_metrics({"available": True, "dhash_similarity": 1.25}),
            1.0,
        )
        self.assertEqual(
            quality_score_from_native_metrics({"available": True, "dhash_similarity": -0.25}),
            0.0,
        )
        self.assertIsNone(
            quality_score_from_native_metrics({"available": False, "dhash_similarity": 0.9})
        )

    def test_vton_api_returns_native_execution_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            person_path = tmp_path / "person.png"
            garment_path = tmp_path / "garment.png"
            output_path = tmp_path / "output.png"
            write_png_rgb(person_path, _person_image())
            write_png_rgb(garment_path, solid_rgb(64, 64, (40, 90, 210)))

            client = TestClient(create_app())
            response = client.post(
                "/v1/vton/infer",
                json={
                    "request_id": "req-native-vton-test",
                    "person_image_path": str(person_path),
                    "garment_image_path": str(garment_path),
                    "output_image_path": str(output_path),
                    "cache_dir": str(tmp_path / "cache"),
                    "timeout_ms": 5000,
                    "quota_plan": "enterprise",
                },
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["status"], "completed")
            self.assertEqual(body["native_vton"]["schema_version"], "tryops.native_vton_execution.v1")
            self.assertIn("preprocessing", body["native_vton"])
            self.assertIn("image_metrics", body["native_vton"])
            self.assertEqual(
                body["report"]["native_execution"]["schema_version"],
                "tryops.native_vton_execution.v1",
            )
            self.assertIn("native_image_quality", body["report"]["metrics"])

            sidecar = json.loads(output_path.with_suffix(".png.json").read_text(encoding="utf-8"))
            self.assertEqual(
                sidecar["native_execution"]["schema_version"],
                "tryops.native_vton_execution.v1",
            )


def _person_image() -> RgbImage:
    image = bytearray(solid_rgb(80, 96, (240, 240, 240)).pixels)
    width = 80
    for y in range(18, 86):
        for x in range(28, 52):
            index = (y * width + x) * 3
            image[index : index + 3] = bytes([190, 170, 145])
    return RgbImage(width=80, height=96, pixels=bytes(image))


if __name__ == "__main__":
    unittest.main()
