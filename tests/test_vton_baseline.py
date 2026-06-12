from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.vton_baseline import run_naive_overlay_baseline
from tryops.simple_image import read_png_rgb, solid_rgb, write_png_rgb


class VtonBaselineTests(unittest.TestCase):
    def test_naive_overlay_baseline_writes_output_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person = root / "person.png"
            garment = root / "garment.png"
            output = root / "output.png"
            write_png_rgb(person, solid_rgb(120, 160, (20, 30, 40)))
            write_png_rgb(garment, solid_rgb(80, 80, (220, 10, 20)))

            report = run_naive_overlay_baseline(
                person_image_path=person,
                garment_image_path=garment,
                output_image_path=output,
                cache_dir=root / "cache",
            )

            self.assertTrue(output.exists())
            self.assertTrue(output.with_suffix(".png.json").exists())
            self.assertEqual(report["model"]["name"], "naive-overlay-vton")
            self.assertIn("run_context", report)
            self.assertIn("run_id", report["lineage"])
            self.assertIn("trace_id", report["lineage"])
            self.assertEqual(report["output"]["width"], 120)
            self.assertEqual(report["output"]["height"], 160)
            self.assertTrue(report["output"]["checksum"].startswith("sha256:"))
            self.assertGreaterEqual(report["metrics"]["latency_ms"], 0)
            self.assertIn("stage_latency_ms", report["metrics"])
            self.assertIn("preflight", report["metrics"]["stage_latency_ms"])
            self.assertIn("optional_preprocessing", report["metrics"]["stage_latency_ms"])
            self.assertIn("generation", report["metrics"]["stage_latency_ms"])
            self.assertIn("optional_segmentation", report["preprocessing"])
            self.assertIn("optional_pose", report["preprocessing"])
            self.assertTrue(report["preprocessing"]["optional_segmentation"]["person_mask"]["checksum"].startswith("sha256:"))
            self.assertTrue(report["preprocessing"]["optional_segmentation"]["garment_mask"]["checksum"].startswith("sha256:"))
            self.assertIn("person", report["preprocessing"]["optional_segmentation"]["native"])
            self.assertIn("garment", report["preprocessing"]["optional_segmentation"]["native"])
            self.assertIn("person_mask_checksum", report["lineage"])
            self.assertIn("garment_mask_checksum", report["lineage"])
            self.assertEqual(
                report["lineage"]["adapter"],
                "tryops.pipelines.vton_baseline.run_naive_overlay_baseline",
            )

            image = read_png_rgb(output)
            overlay_x = report["preprocessing"]["overlay"]["x"]
            overlay_y = report["preprocessing"]["overlay"]["y"]
            index = (overlay_y * image.width + overlay_x) * 3
            self.assertEqual(image.pixels[index : index + 3], bytes([220, 10, 20]))


if __name__ == "__main__":
    unittest.main()
