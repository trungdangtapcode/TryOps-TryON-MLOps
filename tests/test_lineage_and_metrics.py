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

from tryops.contracts import ModelCandidate
from tryops.lineage import build_lineage_record, build_openlineage_run_event
from tryops.native_openlineage import validate_openlineage_event
from tryops.pipelines.llm_benchmark import summarize_llm_benchmark
from tryops.pipelines.vton_eval import summarize_vton_results


class LineageAndMetricsTests(unittest.TestCase):
    def test_lineage_contains_core_evidence(self) -> None:
        payload = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        candidate = ModelCandidate.from_dict(payload)
        record = build_lineage_record(
            candidate,
            request_id="req-001",
            output_uri="s3://tryops-artifacts/outputs/req-001.png",
        )
        self.assertEqual(record["candidate_id"], candidate.candidate_id)
        self.assertEqual(record["lineage"]["dataset_version"], "vitonhd-demo-v1")
        self.assertIn("evaluation_report", record["artifacts"])
        self.assertEqual(record["provenance"]["predicate_type"], "https://slsa.dev/provenance/v1")
        self.assertTrue(record["provenance"]["verified"])

    def test_openlineage_run_event_contains_standard_envelope(self) -> None:
        payload = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        candidate = ModelCandidate.from_dict(payload)
        lineage = build_lineage_record(
            candidate,
            request_id="req-001",
            output_uri="s3://tryops-artifacts/outputs/req-001.png",
        )
        event = build_openlineage_run_event(
            candidate,
            run_context={
                "run_id": "run-vton-001",
                "trace_id": "trace-promotion-vton-catvton-001",
                "created_at": "2026-06-11T00:00:00+00:00",
                "code": {"version": "local-dev"},
            },
            lineage_record=lineage,
        )

        self.assertEqual(event["eventType"], "COMPLETE")
        self.assertEqual(event["eventTime"], "2026-06-11T00:00:00Z")
        self.assertEqual(event["job"]["namespace"], "tryops.local")
        self.assertEqual(event["job"]["name"], "vton.local-promotion-pipeline")
        self.assertEqual(event["inputs"][0]["namespace"], "tryops.dataset")
        self.assertEqual(event["outputs"][0]["namespace"], "tryops.artifact")
        self.assertIn("RunEvent", event["schemaURL"])
        self.assertEqual(len(event["run"]["runId"]), 36)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "openlineage_run_event.json"
            path.write_text(json.dumps(event, indent=2, sort_keys=True), encoding="utf-8")
            validation = validate_openlineage_event(path)
        self.assertTrue(validation["passed"], validation)
        self.assertEqual(validation["event_type"], "COMPLETE")

    def test_vton_summary_outputs_promotion_metrics(self) -> None:
        metrics = summarize_vton_results(
            [
                {
                    "garment_fidelity": 0.8,
                    "identity_preservation": 0.75,
                    "artifact_flag": 0,
                    "latency_ms": 1000,
                },
                {
                    "garment_fidelity": 0.9,
                    "identity_preservation": 0.85,
                    "artifact_flag": 1,
                    "latency_ms": 2000,
                },
            ]
        )
        self.assertEqual(metrics["garment_fidelity"], 0.85)
        self.assertEqual(metrics["artifact_rate"], 0.5)
        self.assertEqual(metrics["latency_p95_ms"], 2000)

    def test_llm_summary_outputs_promotion_metrics(self) -> None:
        metrics = summarize_llm_benchmark(
            [
                {
                    "quality_score": 0.8,
                    "tokens_per_second": 25,
                    "latency_ms": 1100,
                    "memory_gb": 5.5,
                },
                {
                    "quality_score": 0.9,
                    "tokens_per_second": 35,
                    "latency_ms": 1900,
                    "memory_gb": 6.0,
                },
            ]
        )
        self.assertEqual(metrics["quality_score"], 0.85)
        self.assertEqual(metrics["tokens_per_second"], 30.0)
        self.assertEqual(metrics["memory_gb"], 6.0)


if __name__ == "__main__":
    unittest.main()
