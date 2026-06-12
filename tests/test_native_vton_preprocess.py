from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_vton_preprocess import serialize_image_for_native_preprocess  # noqa: E402
from tryops.simple_image import solid_rgb  # noqa: E402


class NativeVtonPreprocessTests(unittest.TestCase):
    def test_serialize_image_for_native_preprocess_wire_format(self) -> None:
        image = solid_rgb(2, 3, (10, 20, 30))
        wire = serialize_image_for_native_preprocess(image, role="person")

        self.assertIn("role=person", wire)
        self.assertIn("width=2", wire)
        self.assertIn("height=3", wire)
        self.assertIn("pixels_hex=", wire)

    def test_serialize_image_for_native_preprocess_rejects_bad_role(self) -> None:
        image = solid_rgb(2, 2, (10, 20, 30))

        with self.assertRaises(ValueError):
            serialize_image_for_native_preprocess(image, role="background")


if __name__ == "__main__":
    unittest.main()
