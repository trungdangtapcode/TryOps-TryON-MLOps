from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.vton_comparison import compare_vton_baselines
from tryops.simple_image import solid_rgb, write_png_rgb


class VtonComparisonTests(unittest.TestCase):
    def test_compare_vton_baselines_writes_comparison_and_gallery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person = root / "person.png"
            garment = root / "garment.png"
            output_dir = root / "comparison"
            write_png_rgb(person, solid_rgb(128, 160, (20, 30, 40)))
            write_png_rgb(garment, solid_rgb(80, 80, (220, 10, 20)))

            comparison = compare_vton_baselines(
                person_image_path=person,
                garment_image_path=garment,
                output_dir=output_dir,
                cache_dir=root / "cache",
            )

            self.assertEqual(len(comparison["runs"]), 2)
            self.assertTrue((output_dir / "comparison.json").exists())
            self.assertTrue((output_dir / "error_gallery.json").exists())
            self.assertIn("winner_by_structural_similarity", comparison)
            self.assertIn("winner_by_perceptual_hash", comparison)
            self.assertIn("winner_by_garment_similarity_proxy", comparison)
            for run in comparison["runs"]:
                self.assertTrue(Path(run["output_path"]).exists())
                self.assertIn("global_ssim_luma", run["metrics_against_person"])
                self.assertIn("dhash_similarity", run["metrics_against_person"])
                self.assertIn("native", run["metrics_against_person"])
                self.assertIn("garment_similarity", run)
                self.assertIn("proxy", run["garment_similarity"])
                self.assertIn("clip", run["garment_similarity"])
                self.assertIn("failure_labels", run)


if __name__ == "__main__":
    unittest.main()
