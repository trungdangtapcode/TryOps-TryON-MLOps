from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.observability import (  # noqa: E402
    configure_structured_log_path,
    configure_trace_span_path,
    metrics_snapshot,
    read_structured_log_file,
    read_trace_span_file,
    record_api_observation,
    render_prometheus_metrics,
    reset_metrics,
    sanitize_payload_metadata,
    start_timer,
    structured_logs_snapshot,
    trace_spans_snapshot,
)
from tryops.trace_envelope import validate_native_trace_log_envelope  # noqa: E402


class ObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_metrics()

    def test_payload_metadata_does_not_store_prompt_text_or_image_paths(self) -> None:
        llm_metadata = sanitize_payload_metadata(
            workload="llm",
            payload={
                "prompt": "secret text should not be stored",
                "model_alias": "baseline",
                "user_id": "customer-123",
                "fallback_enabled": True,
            },
        )
        vton_metadata = sanitize_payload_metadata(
            workload="vton",
            payload={"person_image_path": "/unsafe/person.png", "garment_image_path": "/unsafe/garment.png"},
        )

        self.assertEqual(llm_metadata["prompt_chars"], 32)
        self.assertTrue(llm_metadata["fallback_enabled"])
        self.assertIn("user_hash", llm_metadata)
        self.assertNotIn("customer-123", str(llm_metadata))
        self.assertNotIn("prompt", llm_metadata)
        self.assertNotIn("/unsafe/person.png", str(vton_metadata))
        self.assertEqual(vton_metadata["image_count"], 2)

    def test_record_api_observation_tracks_latency_status_model_and_tokens(self) -> None:
        event = record_api_observation(
            endpoint="/v1/llm/generate",
            request_id="req-observe",
            workload="llm",
            model_alias="baseline",
            status="completed",
            started_at=start_timer(),
            payload={"prompt": "Explain TryOps MLOps.", "model_alias": "baseline", "user_id": "customer-123"},
            response={
                "model": {"version": "0.1.0"},
                "metrics": {
                    "tokens_per_second": 100.0,
                    "memory_gb": 0.01,
                    "phase_timing": {
                        "available": True,
                        "source": "unit-test",
                        "prefill_ms": 2.0,
                        "decode_ms": 4.0,
                    },
                },
                "status": "completed",
            },
        )
        snapshot = metrics_snapshot()
        prometheus = render_prometheus_metrics()

        self.assertEqual(event["model_version"], "0.1.0")
        self.assertEqual(event["tokens_per_second"], 100.0)
        self.assertEqual(event["llm_prefill_ms"], 2.0)
        self.assertEqual(event["llm_decode_ms"], 4.0)
        self.assertEqual(len(event["trace"]["trace_id"]), 32)
        self.assertEqual(len(event["trace"]["span_id"]), 16)
        self.assertTrue(event["traceparent"].startswith("00-"))
        self.assertEqual(snapshot["request_counters"][0]["count"], 1)
        self.assertEqual(len(snapshot["trace_spans"]), 1)
        self.assertIn("tryops_api_latency_ms_sum", prometheus)
        self.assertIn("tryops_trace_spans_total", prometheus)
        self.assertIn("tryops_llm_phase_latency_ms_sum", prometheus)
        self.assertIn('phase="prefill"', prometheus)
        self.assertIn("tryops_api_requests_total", prometheus)

    def test_structured_logs_and_trace_spans_are_sanitized_and_file_backed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "api_events.jsonl"
            span_path = Path(temp_dir) / "api_spans.jsonl"
            configure_structured_log_path(log_path, truncate=True)
            configure_trace_span_path(span_path, truncate=True)
            try:
                record_api_observation(
                    endpoint="/v1/llm/generate",
                    request_id="req-log",
                    workload="llm",
                    model_alias="baseline",
                    status="rejected",
                    started_at=start_timer(),
                    payload={
                        "prompt": "secret prompt must not be logged",
                        "model_alias": "baseline",
                        "user_id": "customer-456",
                    },
                    response={
                        "status": "rejected",
                        "error": {"code": "invalid_llm_request"},
                    },
                )
                memory_records = structured_logs_snapshot()
                memory_spans = trace_spans_snapshot()
                file_records = read_structured_log_file(log_path)
                file_spans = read_trace_span_file(span_path)
            finally:
                configure_structured_log_path(None)
                configure_trace_span_path(None)

        self.assertEqual(len(memory_records), 1)
        self.assertEqual(len(memory_spans), 1)
        self.assertEqual(len(file_records), 1)
        self.assertEqual(len(file_spans), 1)
        self.assertEqual(file_records[0]["schema_version"], "tryops.structured_log.v1")
        self.assertEqual(file_spans[0]["schema_version"], "tryops.trace_span.v1")
        self.assertEqual(file_records[0]["native_envelope"]["schema_version"], "tryops.native_trace_log_envelope.v1")
        self.assertEqual(validate_native_trace_log_envelope(file_records[0]["native_envelope"]), [])
        self.assertEqual(file_records[0]["native_envelope"]["trace_id"], file_spans[0]["trace_id"])
        self.assertEqual(file_records[0]["severity_text"], "ERROR")
        self.assertEqual(file_records[0]["attributes"]["error_code"], "invalid_llm_request")
        self.assertEqual(file_records[0]["trace_id"], file_spans[0]["trace_id"])
        self.assertNotIn("secret prompt", str(file_records[0]))
        self.assertNotIn("secret prompt", str(file_spans[0]))
        self.assertNotIn("customer-456", str(file_records[0]))
        self.assertNotIn("customer-456", str(file_spans[0]))


if __name__ == "__main__":
    unittest.main()
