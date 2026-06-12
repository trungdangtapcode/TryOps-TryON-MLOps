from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.quota import (  # noqa: E402
    QuotaRequest,
    UsageQuotaLedger,
    check_and_record_quota,
    quota_snapshot,
    reset_quota_usage,
    user_hash,
)


class QuotaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, {"TRYOPS_QUOTA_GATEWAY_URL": ""})
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)
        reset_quota_usage()

    def test_quota_ledger_records_usage_and_remaining_capacity(self) -> None:
        ledger = UsageQuotaLedger()

        decision = ledger.check_and_record(
            QuotaRequest(
                user_id="user-a",
                plan="free",
                workload="llm",
                estimated_tokens=300,
            )
        )

        self.assertTrue(decision["allowed"])
        dimensions = {check["dimension"]: check for check in decision["checks"]}
        self.assertEqual(dimensions["llm_requests_per_day"]["used_after"], 1)
        self.assertEqual(dimensions["llm_tokens_per_day"]["used_after"], 300)
        self.assertNotIn("user-a", decision["user_hash"])

    def test_quota_ledger_rejects_over_limit_request_without_incrementing(self) -> None:
        ledger = UsageQuotaLedger()

        decision = ledger.check_and_record(
            QuotaRequest(
                user_id="user-a",
                plan="free",
                workload="llm",
                estimated_tokens=5_001,
            )
        )

        self.assertFalse(decision["allowed"])
        token_check = next(check for check in decision["checks"] if check["dimension"] == "llm_tokens_per_day")
        self.assertEqual(token_check["used_after"], 0)
        self.assertEqual(decision["reason"], "quota_exceeded")

    def test_global_quota_snapshot_uses_hashed_user_id(self) -> None:
        decision = check_and_record_quota(
            user_id="enterprise-user",
            plan="team",
            workload="vton",
            request_units=1,
        )
        snapshot = quota_snapshot()

        self.assertTrue(decision["allowed"])
        self.assertEqual(snapshot["usage"][0]["user_hash"], user_hash("enterprise-user"))
        self.assertNotIn("enterprise-user", str(snapshot))

    def test_global_quota_can_delegate_to_rust_gateway(self) -> None:
        gateway_response = {
            "schema_version": "tryops.quota_decision.v1",
            "engine": "native_rust_gateway",
            "allowed": True,
            "period": "2026-06-11",
            "user_hash": user_hash("enterprise-user"),
            "plan": "team",
            "workload": "vton",
            "checks": [],
            "reason": "within_quota",
        }

        class FakeHttpResponse:
            def __enter__(self) -> "FakeHttpResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(gateway_response).encode("utf-8")

        with patch.dict(os.environ, {"TRYOPS_QUOTA_GATEWAY_URL": "http://127.0.0.1:18086"}), patch(
            "tryops.quota.urllib.request.urlopen",
            return_value=FakeHttpResponse(),
        ) as urlopen:
            decision = check_and_record_quota(
                user_id="enterprise-user",
                plan="team",
                workload="vton",
                request_units=1,
            )

        self.assertEqual(decision["engine"], "native_rust_gateway")
        self.assertTrue(decision["allowed"])
        self.assertEqual(urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
