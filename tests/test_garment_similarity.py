from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.garment_similarity import (  # noqa: E402
    crop_rgb,
    evaluate_garment_similarity,
    proxy_garment_image_similarity,
    rgb_histogram_intersection,
)
from tryops.simple_image import RgbImage, solid_rgb, write_png_rgb  # noqa: E402


class GarmentSimilarityTests(unittest.TestCase):
    def test_proxy_scores_identical_patch_high(self) -> None:
        garment = solid_rgb(6, 6, (20, 80, 200))
        candidate = solid_rgb(6, 6, (20, 80, 200))

        score = proxy_garment_image_similarity(garment, candidate)

        self.assertGreaterEqual(score["score"], 0.99)
        self.assertEqual(score["histogram_similarity"], 1.0)

    def test_histogram_similarity_drops_for_different_colors(self) -> None:
        garment = solid_rgb(6, 6, (20, 80, 200))
        candidate = solid_rgb(6, 6, (200, 20, 40))

        self.assertLess(rgb_histogram_intersection(garment, candidate), 1.0)

    def test_crop_rgb_extracts_overlay_patch(self) -> None:
        image = _output_with_patch()

        patch = crop_rgb(image, {"x": 2, "y": 2, "width": 4, "height": 4})

        self.assertEqual(patch.width, 4)
        self.assertEqual(patch.height, 4)
        self.assertEqual(patch.pixels[:3], bytes([20, 80, 200]))

    def test_evaluate_garment_similarity_reports_proxy_and_clip_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            garment_path = root / "garment.png"
            output_path = root / "output.png"
            write_png_rgb(garment_path, solid_rgb(4, 4, (20, 80, 200)))
            write_png_rgb(output_path, _output_with_patch())

            result = evaluate_garment_similarity(
                garment_image_path=garment_path,
                output_image_path=output_path,
                overlay={"x": 2, "y": 2, "width": 4, "height": 4},
            )

            self.assertEqual(result["schema_version"], "tryops.garment_similarity.v1")
            self.assertGreaterEqual(result["proxy"]["score"], 0.99)
            self.assertIn("clip", result)
            self.assertFalse(result["clip"]["enabled"])

    def test_crop_rgb_rejects_out_of_bounds_overlay(self) -> None:
        with self.assertRaises(ValueError):
            crop_rgb(solid_rgb(4, 4, (0, 0, 0)), {"x": 3, "y": 3, "width": 2, "height": 2})


def _output_with_patch() -> RgbImage:
    pixels = bytearray(solid_rgb(8, 8, (180, 180, 180)).pixels)
    for y in range(2, 6):
        for x in range(2, 6):
            index = (y * 8 + x) * 3
            pixels[index : index + 3] = bytes([20, 80, 200])
    return RgbImage(width=8, height=8, pixels=bytes(pixels))


if __name__ == "__main__":
    unittest.main()
