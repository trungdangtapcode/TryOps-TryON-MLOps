from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.data_ingestion import (
    build_manifest_entry,
    detect_image_format,
    read_image_metadata,
    sha256_file,
    validate_image_file,
)


def png_bytes(width: int = 128, height: int = 96, color_type: int = 2) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, color_type, 0, 0, 0])
        + b"\x00\x00\x00\x00"
    )


def jpeg_bytes(width: int = 128, height: int = 96, components: int = 3) -> bytes:
    segment = (
        b"\xff\xc0"
        + (8 + 3 * components).to_bytes(2, "big")
        + b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + bytes([components])
        + b"\x01\x11\x00" * components
    )
    return b"\xff\xd8" + segment + b"\xff\xd9"


class DataIngestionTests(unittest.TestCase):
    def test_sha256_file_uses_prefixed_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.bin"
            path.write_bytes(b"tryops")
            self.assertTrue(sha256_file(path).startswith("sha256:"))

    def test_detect_png_and_jpeg_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            png = Path(temp_dir) / "sample.png"
            jpeg = Path(temp_dir) / "sample.jpg"
            png.write_bytes(png_bytes())
            jpeg.write_bytes(jpeg_bytes())
            self.assertEqual(detect_image_format(png), "png")
            self.assertEqual(detect_image_format(jpeg), "jpeg")

    def test_read_image_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            png = Path(temp_dir) / "sample.png"
            jpeg = Path(temp_dir) / "sample.jpg"
            png.write_bytes(png_bytes(width=256, height=192, color_type=6))
            jpeg.write_bytes(jpeg_bytes(width=300, height=200))
            self.assertEqual(
                read_image_metadata(png),
                {"format": "png", "width": 256, "height": 192, "color_mode": "rgba"},
            )
            self.assertEqual(
                read_image_metadata(jpeg),
                {"format": "jpeg", "width": 300, "height": 200, "color_mode": "rgb"},
            )

    def test_validate_rejects_unknown_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.txt"
            path.write_text("not image", encoding="utf-8")
            report = validate_image_file(path)
            self.assertFalse(report["passed"])
            self.assertIn("unsupported", " ".join(report["errors"]))

    def test_validate_rejects_too_small_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.png"
            path.write_bytes(png_bytes(width=32, height=32))
            report = validate_image_file(path)
            self.assertFalse(report["passed"])
            self.assertIn("below minimum", " ".join(report["errors"]))

    def test_build_manifest_entry_adds_checksum_and_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.png"
            path.write_bytes(png_bytes())
            entry = build_manifest_entry(
                item_id="demo-001",
                path=path,
                split="demo",
                license_name="public-demo",
            )
            self.assertEqual(entry["format"], "png")
            self.assertEqual(entry["width"], 128)
            self.assertEqual(entry["height"], 96)
            self.assertEqual(entry["color_mode"], "rgb")
            self.assertTrue(entry["checksum"].startswith("sha256:"))
            self.assertEqual(entry["split"], "demo")


if __name__ == "__main__":
    unittest.main()

