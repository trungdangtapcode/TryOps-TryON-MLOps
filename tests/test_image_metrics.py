from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.image_metrics import (
    compare_images,
    compare_png_files,
    difference_hash_distance,
    edge_delta,
    global_ssim_luma,
    mean_squared_error,
    psnr,
)
from tryops.simple_image import solid_rgb, write_png_rgb


class ImageMetricsTests(unittest.TestCase):
    def test_identical_images_have_perfect_scores(self) -> None:
        left = solid_rgb(8, 8, (10, 20, 30))
        right = solid_rgb(8, 8, (10, 20, 30))
        self.assertEqual(mean_squared_error(left, right), 0.0)
        self.assertEqual(psnr(left, right), float("inf"))
        self.assertEqual(global_ssim_luma(left, right), 1.0)
        self.assertEqual(difference_hash_distance(left, right), 0)
        self.assertEqual(edge_delta(left, right), 0.0)

    def test_different_images_have_lower_similarity(self) -> None:
        left = solid_rgb(8, 8, (0, 0, 0))
        right = solid_rgb(8, 8, (255, 255, 255))
        self.assertGreater(mean_squared_error(left, right), 0)
        self.assertLess(global_ssim_luma(left, right), 1.0)

    def test_compare_png_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            left = Path(temp_dir) / "left.png"
            right = Path(temp_dir) / "right.png"
            write_png_rgb(left, solid_rgb(8, 8, (10, 20, 30)))
            write_png_rgb(right, solid_rgb(8, 8, (15, 25, 35)))
            metrics = compare_png_files(left, right)
            self.assertIn("mse", metrics)
            self.assertIn("psnr", metrics)
            self.assertIn("global_ssim_luma", metrics)
            self.assertIn("dhash_similarity", metrics)

    def test_compare_images_includes_perceptual_proxy_metrics(self) -> None:
        left = solid_rgb(8, 8, (10, 20, 30))
        right = solid_rgb(8, 8, (30, 20, 10))
        metrics = compare_images(left, right)
        self.assertIn("dhash_distance", metrics)
        self.assertIn("dhash_similarity", metrics)
        self.assertIn("edge_delta", metrics)
        self.assertGreaterEqual(metrics["dhash_similarity"], 0.0)
        self.assertLessEqual(metrics["dhash_similarity"], 1.0)


if __name__ == "__main__":
    unittest.main()
