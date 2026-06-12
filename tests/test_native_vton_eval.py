from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_vton_eval import serialize_vton_eval_for_native  # noqa: E402
from tryops.simple_image import solid_rgb  # noqa: E402


class NativeVtonEvalTests(unittest.TestCase):
    def test_serialize_vton_eval_wire_format_includes_study_rows(self) -> None:
        person = solid_rgb(4, 4, (20, 30, 40))
        garment = solid_rgb(2, 2, (200, 10, 20))
        output = solid_rgb(4, 4, (20, 30, 40))

        wire = serialize_vton_eval_for_native(
            person=person,
            garment=garment,
            output=output,
            overlay={"x": 1, "y": 1, "width": 2, "height": 2},
            preferences=[{"winner": "a", "loser": "b", "weight": 1.0}],
            fairness_slices=[{"skin_tone": "medium", "body_type": "straight", "quality": 0.88}],
        )

        self.assertIn("person.width=4", wire)
        self.assertIn("garment.pixels_hex=", wire)
        self.assertIn("overlay.x=1", wire)
        self.assertIn("preference.0.winner=a", wire)
        self.assertIn("slice.0.skin_tone=medium", wire)

    def test_serialize_vton_eval_requires_matching_person_and_output_sizes(self) -> None:
        with self.assertRaises(ValueError):
            serialize_vton_eval_for_native(
                person=solid_rgb(4, 4, (20, 30, 40)),
                garment=solid_rgb(2, 2, (200, 10, 20)),
                output=solid_rgb(5, 4, (20, 30, 40)),
                overlay={"x": 1, "y": 1, "width": 2, "height": 2},
                preferences=[],
                fairness_slices=[],
            )


if __name__ == "__main__":
    unittest.main()
