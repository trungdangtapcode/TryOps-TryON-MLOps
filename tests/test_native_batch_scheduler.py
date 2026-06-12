from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_continuous_batching import build_mixed_request_stream
from tryops.native_batch_scheduler import (
    evaluate_with_native_batch_scheduler,
    serialize_scheduler_payload,
)


class NativeBatchSchedulerTests(unittest.TestCase):
    def test_serialize_scheduler_payload_contains_request_arrays(self) -> None:
        payload = serialize_scheduler_payload(
            [
                {"arrival_ms": 0.0, "prefill_tokens": 64, "decode_tokens": 8},
                {"arrival_ms": 1.5, "prefill_tokens": 256, "decode_tokens": 32},
            ],
            max_num_seqs=2,
        )

        self.assertIn("request.arrival_ms=0.0,1.5", payload)
        self.assertIn("request.prefill_tokens=64.0,256.0", payload)
        self.assertIn("request.decode_tokens=8,32", payload)
        self.assertIn("config.max_num_seqs=2", payload)

    def test_missing_native_cli_degrades_with_unavailable_result(self) -> None:
        result = evaluate_with_native_batch_scheduler(
            [{"arrival_ms": 0.0, "prefill_tokens": 64, "decode_tokens": 8}],
            cli_path=Path("/tmp/tryops-missing-batch-scheduler-cli"),
        )

        self.assertFalse(result["available"])
        self.assertEqual(result["schema_version"], "tryops.native_batch_scheduler.v1")

    def test_build_mixed_request_stream_from_sensitivity(self) -> None:
        sensitivity = {
            "prompt_length_sensitivity": [
                {"actual_input_tokens": 16},
                {"actual_input_tokens": 64},
            ],
            "output_length_sensitivity": [
                {"max_tokens": 8, "output_tokens": 8},
                {"max_tokens": 32, "output_tokens": 32},
            ],
        }

        requests = build_mixed_request_stream(sensitivity, concurrency=2, arrival_stride_ms=3.0)

        self.assertEqual(len(requests), 4)
        self.assertEqual(requests[0]["arrival_ms"], 0.0)
        self.assertEqual(requests[2]["arrival_ms"], 3.0)
        self.assertEqual({request["decode_tokens"] for request in requests}, {8, 32})

    def test_bridge_parses_native_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cli = Path(tmpdir) / "scheduler"
            cli.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "sys.stdin.read()\n"
                "print(json.dumps({'schema_version':'tryops.native_batch_scheduler.v1','passed':True}))\n",
                encoding="utf-8",
            )
            cli.chmod(0o755)

            result = evaluate_with_native_batch_scheduler(
                [{"arrival_ms": 0.0, "prefill_tokens": 64, "decode_tokens": 8}],
                cli_path=cli,
            )

        self.assertTrue(result["available"])
        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
