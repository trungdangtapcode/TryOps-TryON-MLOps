from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_phase_timing import build_phase_timing, summarize_phase_timing  # noqa: E402


class LLMPhaseTimingTests(unittest.TestCase):
    def test_build_phase_timing_records_rates_and_semantics(self) -> None:
        timing = build_phase_timing(
            input_tokens=100,
            output_tokens=20,
            prefill_ms=50.0,
            decode_ms=100.0,
            source="unit-test",
            semantics="measured",
            total_latency_ms=160.0,
        )

        self.assertEqual(timing["schema_version"], "tryops.llm_phase_timing.v1")
        self.assertEqual(timing["prefill_ms"], 50.0)
        self.assertEqual(timing["decode_ms"], 100.0)
        self.assertEqual(timing["prefill_tokens_per_second"], 2000.0)
        self.assertEqual(timing["decode_tokens_per_second"], 200.0)
        self.assertEqual(timing["total_latency_ms"], 160.0)

    def test_summarize_phase_timing_ignores_missing_records(self) -> None:
        summary = summarize_phase_timing(
            [
                {"phase_timing": build_phase_timing(input_tokens=10, output_tokens=5, prefill_ms=2, decode_ms=4, source="a", semantics="measured")},
                {"phase_timing": build_phase_timing(input_tokens=20, output_tokens=5, prefill_ms=6, decode_ms=8, source="a", semantics="measured")},
                {},
            ]
        )

        self.assertTrue(summary["available"])
        self.assertEqual(summary["record_count"], 2)
        self.assertEqual(summary["prefill_avg_ms"], 4.0)
        self.assertEqual(summary["decode_p95_ms"], 8.0)


if __name__ == "__main__":
    unittest.main()
