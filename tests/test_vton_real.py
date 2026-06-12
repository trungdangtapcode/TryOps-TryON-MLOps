from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tryops.pipelines.vton_real as vr  # noqa: E402

DEMO = ROOT / "artifacts" / "demo" / "vton"


class VtonRealFallbackTests(unittest.TestCase):
    """The real diffusion path must degrade to the deterministic baseline and
    still emit the unchanged tryops.vton_baseline.v1 contract."""

    def setUp(self) -> None:
        # Ensure demo inputs exist (created by create_synthetic_vton_demo).
        if not (DEMO / "person.png").exists():
            from scripts import create_synthetic_vton_demo  # noqa: F401

    def test_falls_back_to_baseline_without_gpu(self) -> None:
        if not (DEMO / "person.png").exists():
            self.skipTest("demo images not generated")
        original = vr.real_vton_available
        vr.real_vton_available = lambda: False  # force the offline/no-GPU path
        try:
            report = vr.run_real_vton(
                person_image_path=DEMO / "person.png",
                garment_image_path=DEMO / "garment.png",
                output_image_path=DEMO / "real_fallback_test.png",
                cache_dir=ROOT / "artifacts" / "cache" / "vton_preflight",
            )
        finally:
            vr.real_vton_available = original
        self.assertEqual(report["schema_version"], "tryops.vton_baseline.v1")
        self.assertIn("fallback_reason", report["model"])
        self.assertIn("output", report)
        self.assertIn("lineage", report)

    def test_composite_and_mask_shapes(self) -> None:
        if not (DEMO / "person.png").exists():
            self.skipTest("demo images not generated")
        composite, mask, region = vr._composite_and_mask(
            DEMO / "person.png", DEMO / "garment.png"
        )
        self.assertEqual(composite.size, (512, 512))
        self.assertEqual(mask.size, (512, 512))
        self.assertTrue(region["width"] > 0 and region["height"] > 0)


if __name__ == "__main__":
    unittest.main()
