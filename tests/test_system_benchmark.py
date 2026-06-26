from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.system_benchmark import (  # noqa: E402
    build_system_benchmark_report,
    discover_vton_dataset_pairs,
    render_markdown_report,
    summarize_records,
)


class SystemBenchmarkTests(unittest.TestCase):
    def test_discovers_viton_style_pairs_from_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "test_img").mkdir()
            (root / "test_color").mkdir()
            (root / "test_img" / "000001_0.jpg").write_bytes(b"person")
            (root / "test_img" / "000002_0.jpg").write_bytes(b"person")
            (root / "test_color" / "000001_1.jpg").write_bytes(b"garment")
            (root / "test_color" / "000002_1.jpg").write_bytes(b"garment")

            pairs = discover_vton_dataset_pairs(root, limit=2)

            self.assertEqual([pair["pair_id"] for pair in pairs], ["000001", "000002"])
            self.assertTrue(pairs[0]["person_image"].endswith("000001_0.jpg"))
            self.assertTrue(pairs[0]["garment_image"].endswith("000001_1.jpg"))

    def test_summarizes_records_for_mlflow_and_report_table(self) -> None:
        records = [
            {
                "workload": "vton",
                "scenario": "vton_job_real",
                "target": "fashn-vton-1.5",
                "ok": True,
                "latency_ms": 100.0,
                "started_epoch_ms": 1000,
                "ended_epoch_ms": 1100,
                "metrics": {
                    "model_latency_ms": 80.0,
                    "quality_score": 0.7,
                    "ssim": 0.8,
                    "psnr": 22.0,
                    "system_cpu_percent_avg": 12.0,
                    "system_memory_used_gb_max": 8.5,
                    "system_gpu_util_percent_max": 71.0,
                    "system_gpu_memory_used_gb_max": 3.2,
                },
            },
            {
                "workload": "vton",
                "scenario": "vton_job_real",
                "target": "fashn-vton-1.5",
                "ok": False,
                "latency_ms": 300.0,
                "started_epoch_ms": 1100,
                "ended_epoch_ms": 1400,
                "metrics": {
                    "model_latency_ms": 250.0,
                    "quality_score": 0.3,
                    "ssim": 0.6,
                    "psnr": 18.0,
                    "system_cpu_percent_avg": 18.0,
                    "system_memory_used_gb_max": 9.0,
                    "system_gpu_util_percent_max": 66.0,
                    "system_gpu_memory_used_gb_max": 3.0,
                },
            },
        ]

        summary = summarize_records(records)
        self.assertEqual(summary[0]["requests"], 2)
        self.assertEqual(summary[0]["success_rate_percent"], 50.0)
        self.assertEqual(summary[0]["avg_latency_ms"], 200.0)
        self.assertEqual(summary[0]["avg_model_latency_ms"], 165.0)
        self.assertEqual(summary[0]["avg_quality_score"], 0.5)
        self.assertEqual(summary[0]["avg_ssim"], 0.7)
        self.assertEqual(summary[0]["avg_psnr"], 20.0)
        self.assertEqual(summary[0]["avg_system_cpu_percent"], 15.0)
        self.assertEqual(summary[0]["max_system_memory_used_gb"], 9.0)
        self.assertEqual(summary[0]["max_system_gpu_util_percent"], 71.0)
        self.assertEqual(summary[0]["max_system_gpu_memory_used_gb"], 3.2)

        report = build_system_benchmark_report(
            records=records,
            mlflow={"experiment_name": "tryops-system-benchmark", "experiment_url": "http://mlflow"},
            config={"base_url": "http://gateway"},
        )
        markdown = render_markdown_report(report)
        self.assertIn("| Workload | Scenario | Dataset/Target | Samples | Success (%) ↑ | SSIM ↑ | PSNR ↑ |", markdown)
        self.assertIn("GPU util (%)", markdown)
        self.assertIn("vton_job_real", markdown)


if __name__ == "__main__":
    unittest.main()
