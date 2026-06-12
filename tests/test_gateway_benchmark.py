from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.gateway_benchmark import summarize_latencies  # noqa: E402


class SummarizeLatenciesTests(unittest.TestCase):
    def test_throughput_and_percentiles(self) -> None:
        lat = [float(i) for i in range(1, 101)]  # 1..100 ms
        s = summarize_latencies(lat, elapsed_s=1.0, errors=0, total=100)
        self.assertEqual(s["requests_per_sec"], 100.0)
        self.assertEqual(s["latency_ms"]["min"], 1.0)
        self.assertEqual(s["latency_ms"]["max"], 100.0)
        # p50 ~ median, p99 near the top
        self.assertGreaterEqual(s["latency_ms"]["p99"], s["latency_ms"]["p95"])
        self.assertGreaterEqual(s["latency_ms"]["p95"], s["latency_ms"]["p50"])

    def test_empty_latencies_safe(self) -> None:
        s = summarize_latencies([], elapsed_s=1.0, errors=5, total=5)
        self.assertEqual(s["errors"], 5)
        self.assertEqual(s["latency_ms"]["p50"], 0.0)

    def test_zero_elapsed_does_not_divide_by_zero(self) -> None:
        s = summarize_latencies([1.0], elapsed_s=0.0, errors=0, total=1)
        self.assertEqual(s["requests_per_sec"], 0.0)


if __name__ == "__main__":
    unittest.main()
