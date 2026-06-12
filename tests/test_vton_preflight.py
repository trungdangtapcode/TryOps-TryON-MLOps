from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.vton_preflight import build_vton_preflight


def png_bytes(width: int = 128, height: int = 128) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, 2, 0, 0, 0])
        + b"\x00\x00\x00\x00"
    )


class VtonPreflightTests(unittest.TestCase):
    def test_preflight_passes_and_writes_cache_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person = root / "person.png"
            garment = root / "garment.png"
            cache = root / "cache"
            person.write_bytes(png_bytes(width=256, height=384))
            garment.write_bytes(png_bytes(width=256, height=256))

            report = build_vton_preflight(
                person_image_path=person,
                garment_image_path=garment,
                cache_dir=cache,
            )

            self.assertTrue(report["passed"])
            self.assertEqual(report["person"]["width"], 256)
            self.assertEqual(report["garment"]["height"], 256)
            self.assertTrue(report["person"]["checksum"].startswith("sha256:"))
            self.assertIsNotNone(report["cache_key"])
            self.assertTrue((cache / f"{report['cache_key']}.json").exists())
            self.assertGreaterEqual(report["latency_ms"], 0)

    def test_preflight_rejects_too_small_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person = root / "person.png"
            garment = root / "garment.png"
            person.write_bytes(png_bytes(width=32, height=32))
            garment.write_bytes(png_bytes(width=256, height=256))

            report = build_vton_preflight(
                person_image_path=person,
                garment_image_path=garment,
                cache_dir=root / "cache",
            )

            self.assertFalse(report["passed"])
            self.assertIsNone(report["cache_key"])
            self.assertIn("person image", " ".join(report["errors"]))


if __name__ == "__main__":
    unittest.main()

