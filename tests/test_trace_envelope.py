from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.trace_envelope import (  # noqa: E402
    build_native_trace_log_envelope,
    validate_native_trace_log_envelope,
)


class TraceEnvelopeTests(unittest.TestCase):
    def test_fastapi_envelope_validates_w3c_traceparent(self) -> None:
        event = {
            "timestamp": "2026-06-12T00:00:00+00:00",
            "request_id": "req-1",
            "workload": "llm",
            "trace_id": "11111111111111111111111111111111",
            "span_id": "2222222222222222",
            "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
            "trace": {"trace_flags": "01"},
            "payload_metadata": {"prompt_chars": 12, "user_hash": "u"},
        }
        envelope = build_native_trace_log_envelope(event)

        self.assertEqual(validate_native_trace_log_envelope(envelope), [])
        self.assertEqual(envelope["resource"]["service.name"], "tryops-api")

    def test_rejects_zero_trace_and_sensitive_attributes(self) -> None:
        event = {
            "request_id": "req-2",
            "workload": "llm",
            "trace_id": "00000000000000000000000000000000",
            "span_id": "2222222222222222",
            "trace": {"trace_flags": "01"},
            "payload_metadata": {"prompt": "secret prompt must not be present"},
        }
        envelope = build_native_trace_log_envelope(event)
        errors = validate_native_trace_log_envelope(envelope)

        self.assertIn("invalid trace_id", errors)
        self.assertIn("attributes contain sensitive raw fields", errors)


if __name__ == "__main__":
    unittest.main()
