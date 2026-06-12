from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_image_metrics import serialize_images_for_native  # noqa: E402
from tryops.simple_image import solid_rgb  # noqa: E402


class NativeImageMetricsTests(unittest.TestCase):
    def test_serialize_images_for_native_wire_format(self) -> None:
        reference = solid_rgb(2, 2, (10, 20, 30))
        candidate = solid_rgb(2, 2, (10, 20, 30))
        wire = serialize_images_for_native(reference, candidate)

        self.assertIn("reference.width=2", wire)
        self.assertIn("reference.height=2", wire)
        self.assertIn("candidate.width=2", wire)
        self.assertIn("candidate.pixels_hex=", wire)

    def test_serialize_images_for_native_requires_matching_sizes(self) -> None:
        reference = solid_rgb(2, 2, (10, 20, 30))
        candidate = solid_rgb(3, 2, (10, 20, 30))

        with self.assertRaises(ValueError):
            serialize_images_for_native(reference, candidate)


if __name__ == "__main__":
    unittest.main()
