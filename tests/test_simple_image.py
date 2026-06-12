from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.simple_image import overlay, read_png_rgb, resize_nearest, solid_rgb, write_png_rgb


class SimpleImageTests(unittest.TestCase):
    def test_png_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "image.png"
            image = solid_rgb(16, 12, (10, 20, 30))
            write_png_rgb(path, image)
            loaded = read_png_rgb(path)
            self.assertEqual(loaded.width, 16)
            self.assertEqual(loaded.height, 12)
            self.assertEqual(loaded.pixels, image.pixels)

    def test_resize_nearest(self) -> None:
        image = solid_rgb(4, 4, (1, 2, 3))
        resized = resize_nearest(image, 2, 3)
        self.assertEqual(resized.width, 2)
        self.assertEqual(resized.height, 3)
        self.assertEqual(resized.pixels, bytes([1, 2, 3]) * 6)

    def test_overlay_changes_target_region(self) -> None:
        base = solid_rgb(4, 4, (0, 0, 0))
        patch = solid_rgb(2, 2, (255, 0, 0))
        output = overlay(base, patch, x=1, y=1)
        center_index = (1 * output.width + 1) * 3
        self.assertEqual(output.pixels[center_index : center_index + 3], bytes([255, 0, 0]))
        self.assertEqual(output.pixels[:3], bytes([0, 0, 0]))


if __name__ == "__main__":
    unittest.main()

