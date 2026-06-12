from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.tracing import build_api_server_span, build_trace_context, parse_traceparent  # noqa: E402


class TracingTests(unittest.TestCase):
    def test_parse_traceparent_accepts_w3c_shape(self) -> None:
        parsed = parse_traceparent("00-11111111111111111111111111111111-2222222222222222-01")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["trace_id"], "11111111111111111111111111111111")
        self.assertEqual(parsed["span_id"], "2222222222222222")

    def test_parse_traceparent_rejects_invalid_or_zero_ids(self) -> None:
        self.assertIsNone(parse_traceparent("not-a-trace"))
        self.assertIsNone(parse_traceparent("00-00000000000000000000000000000000-2222222222222222-01"))
        self.assertIsNone(parse_traceparent("00-11111111111111111111111111111111-0000000000000000-01"))

    def test_build_trace_context_propagates_parent(self) -> None:
        context = build_trace_context(
            {"traceparent": "00-11111111111111111111111111111111-2222222222222222-01"}
        )

        self.assertEqual(context["trace_id"], "11111111111111111111111111111111")
        self.assertEqual(context["parent_span_id"], "2222222222222222")
        self.assertTrue(context["remote_parent"])
        self.assertEqual(len(context["span_id"]), 16)

    def test_server_span_uses_sanitized_attributes(self) -> None:
        span = build_api_server_span(
            endpoint="/v1/llm/generate",
            request_id="req-trace",
            workload="llm",
            model_alias="baseline",
            model_version="0.1.0",
            app_status="completed",
            latency_ms=12.3,
            payload_metadata={"prompt_chars": 17, "quota_plan": "free", "user_hash": "abc123"},
            carrier={"prompt": "secret prompt"},
            phase_timing={"source": "unit-test", "prefill_ms": 1.0, "decode_ms": 2.0},
        )

        self.assertEqual(span["schema_version"], "tryops.trace_span.v1")
        self.assertEqual(span["name"], "POST /v1/llm/generate")
        self.assertEqual(span["kind"], "SERVER")
        self.assertEqual(span["attributes"]["http.request.method"], "POST")
        self.assertEqual(span["attributes"]["http.route"], "/v1/llm/generate")
        self.assertEqual(span["attributes"]["tryops.quota.plan"], "free")
        self.assertNotIn("secret prompt", str(span))


if __name__ == "__main__":
    unittest.main()
