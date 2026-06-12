from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.api import generate_baseline_response, run_naive_overlay_baseline
from tryops.simple_image import solid_rgb, write_png_rgb


class ApiHelperTests(unittest.TestCase):
    def test_api_import_exposes_vton_baseline_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person = root / "person.png"
            garment = root / "garment.png"
            output = root / "output.png"
            write_png_rgb(person, solid_rgb(128, 160, (10, 20, 30)))
            write_png_rgb(garment, solid_rgb(80, 80, (200, 20, 30)))
            report = run_naive_overlay_baseline(
                person_image_path=person,
                garment_image_path=garment,
                output_image_path=output,
                cache_dir=root / "cache",
            )
            self.assertEqual(report["model"]["name"], "naive-overlay-vton")

    def test_api_import_exposes_llm_baseline_adapter(self) -> None:
        response = generate_baseline_response(
            prompt="Compare GPTQ and AWQ for an LLM serving benchmark.",
            model_alias="baseline",
        )
        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["model"]["adapter"], "deterministic-rule-baseline")
        self.assertIn("tokens_per_second", response["metrics"])


if __name__ == "__main__":
    unittest.main()
