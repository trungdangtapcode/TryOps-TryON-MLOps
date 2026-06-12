from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.vton_preprocessing import (  # noqa: E402
    bounding_box,
    build_vton_optional_preprocessing,
    estimate_foreground_mask,
    estimate_pose_hints,
    mask_coverage,
)
from tryops.simple_image import RgbImage, solid_rgb, write_png_rgb  # noqa: E402


class VtonPreprocessingTests(unittest.TestCase):
    def test_foreground_mask_bbox_and_pose_hints(self) -> None:
        image = _foreground_square_image()
        mask = estimate_foreground_mask(image, threshold=32.0)
        bbox = bounding_box(mask, image.width, image.height)
        pose = estimate_pose_hints(bbox, image.width, image.height)

        self.assertEqual(bbox, {"x": 2, "y": 1, "width": 4, "height": 4})
        self.assertAlmostEqual(mask_coverage(mask), 0.25)
        self.assertTrue(pose["available"])
        self.assertIn("neck", pose["keypoints"])
        self.assertIn("left_shoulder", pose["keypoints"])

    def test_build_optional_preprocessing_writes_masks_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person = root / "person.png"
            garment = root / "garment.png"
            write_png_rgb(person, _foreground_square_image())
            write_png_rgb(garment, solid_rgb(6, 6, (20, 80, 200)))

            report = build_vton_optional_preprocessing(
                person_image_path=person,
                garment_image_path=garment,
                cache_dir=root / "cache",
            )

            self.assertEqual(report["schema_version"], "tryops.vton_optional_preprocessing.v1")
            self.assertTrue(Path(report["person_mask"]["path"]).exists())
            self.assertTrue(Path(report["garment_mask"]["path"]).exists())
            self.assertTrue((Path(report["cache_dir"]) / "preprocessing.json").exists())
            self.assertTrue(report["person_mask"]["checksum"].startswith("sha256:"))
            self.assertEqual(report["garment_mask"]["bbox"], {"x": 0, "y": 0, "width": 6, "height": 6})
            self.assertEqual(report["garment_mask"]["coverage"], 1.0)
            self.assertIn("native", report)
            self.assertIn("person", report["native"])

    def test_bounding_box_rejects_wrong_mask_size(self) -> None:
        with self.assertRaises(ValueError):
            bounding_box([True, False], width=3, height=1)


def _foreground_square_image() -> RgbImage:
    image = bytearray(solid_rgb(8, 8, (240, 240, 240)).pixels)
    for y in range(1, 5):
        for x in range(2, 6):
            index = (y * 8 + x) * 3
            image[index : index + 3] = bytes([30, 40, 50])
    return RgbImage(width=8, height=8, pixels=bytes(image))


if __name__ == "__main__":
    unittest.main()
