from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.llm_optimization_report import (  # noqa: E402
    render_metrics_csv,
    render_quality_latency_memory_chart,
    write_llm_optimization_report,
)


def _artifact() -> dict[str, object]:
    return {
        "schema_version": "tryops.llm_pareto.v1",
        "created_at": "2026-06-11T00:00:00+00:00",
        "model_id": "example/model",
        "pareto_frontier": ["none", "4bit"],
        "recommendation": {"variant": "4bit", "reason": "smallest VRAM on frontier"},
        "variants": [
            {
                "variant": "none",
                "available": True,
                "quality_score": 0.5,
                "peak_vram_gb": 1.0,
                "latency_p50_ms": 100.0,
                "tokens_per_second": 20.0,
                "native_perf_stats": {"latency_ms": {"p95": 120.0}},
                "slo": {"verdict": "pass"},
            },
            {
                "variant": "8bit",
                "available": True,
                "quality_score": 0.5,
                "peak_vram_gb": 0.7,
                "latency_p50_ms": 400.0,
                "tokens_per_second": 4.0,
                "native_perf_stats": {"latency_ms": {"p95": 450.0}},
                "slo": {"verdict": "fail"},
            },
            {
                "variant": "4bit",
                "available": True,
                "quality_score": 0.49,
                "peak_vram_gb": 0.4,
                "latency_p50_ms": 180.0,
                "tokens_per_second": 18.0,
                "native_perf_stats": {"latency_ms": {"p95": 210.0}},
                "slo": {"verdict": "pass"},
            },
        ],
    }


class LLMOptimizationReportTests(unittest.TestCase):
    def test_write_report_creates_markdown_chart_csv_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pareto = root / "pareto.json"
            pareto.write_text(json.dumps(_artifact()), encoding="utf-8")

            report = write_llm_optimization_report(pareto_path=pareto, output_dir=root / "report")

            self.assertTrue(report["passed"])
            self.assertEqual(report["recommendation"]["variant"], "4bit")
            markdown = Path(report["artifacts"]["markdown_report"]).read_text(encoding="utf-8")
            chart = Path(report["artifacts"]["chart_svg"]).read_text(encoding="utf-8")
            metrics = Path(report["artifacts"]["metrics_csv"]).read_text(encoding="utf-8")
            self.assertIn("Quality-Latency-Memory Pareto Chart", markdown)
            self.assertIn("Recommended variant: `4bit`", markdown)
            self.assertIn("<svg", chart)
            self.assertIn("4bit", chart)
            self.assertIn("latency_p95_ms", metrics)

    def test_chart_handles_equal_ranges(self) -> None:
        rows = [
            {
                "variant": "same",
                "available": True,
                "quality_score": 0.5,
                "latency_p95_ms": 10.0,
                "tokens_per_second": 2.0,
                "peak_vram_gb": 1.0,
                "slo_verdict": "pass",
                "frontier": "yes",
            }
        ]
        chart = render_quality_latency_memory_chart(rows, {"variant": "same"})
        self.assertIn("<circle", chart)
        self.assertIn("same", chart)

    def test_csv_contains_all_variants(self) -> None:
        rows = [
            {
                "variant": "none",
                "available": True,
                "quality_score": 0.5,
                "latency_p50_ms": 1.0,
                "latency_p95_ms": 2.0,
                "tokens_per_second": 3.0,
                "peak_vram_gb": 4.0,
                "slo_verdict": "pass",
                "frontier": "yes",
                "error": "",
            }
        ]
        csv_text = render_metrics_csv(rows)
        self.assertIn("variant,available,quality_score", csv_text)
        self.assertIn("none,True,0.5", csv_text)


if __name__ == "__main__":
    unittest.main()
