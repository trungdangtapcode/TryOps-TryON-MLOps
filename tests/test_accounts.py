from __future__ import annotations

import os
import sys
import tempfile
from threading import Event
import unittest
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops import db  # noqa: E402
from tryops.jobs import VTON_JOB_QUEUE, reset_job_queue  # noqa: E402
from tryops.quota import reset_quota_usage, user_hash  # noqa: E402

try:
    from fastapi.testclient import TestClient
    from tryops.api import create_app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]
    create_app = None  # type: ignore[assignment]


def _fake_real_llm_response(**kwargs: object) -> dict[str, object]:
    prompt = str(kwargs.get("prompt", ""))
    model_alias = str(kwargs.get("model_alias", "champion"))
    return {
        "schema_version": "tryops.llm_generation.v1",
        "status": "completed",
        "model": {"alias": model_alias, "name": "test-real-model", "adapter": "openai-compatible-vllm"},
        "prompt": {"characters": len(prompt), "estimated_tokens": max(1, len(prompt.split())), "class": "test"},
        "output": {"text": "real model response", "estimated_tokens": 3, "truncated": False},
        "metrics": {"latency_ms": 1.0, "tokens_per_second": 3.0, "memory_gb": 0.0},
        "cost_estimate": {"request_usd": 0.0, "total_tokens": 4, "basis": "test"},
        "safety": {"status": "passed"},
    }


def auth_headers(
    subject: str,
    *,
    email: str = "user@example.com",
    scopes: str | None = None,
    display_name: str | None = None,
) -> dict[str, str]:
    name = display_name or ""
    return {
        "x-tryops-auth-key-id": subject,
        "x-tryops-auth-subject": subject,
        "x-tryops-auth-provider": "keycloak",
        "x-tryops-auth-email": email,
        "x-tryops-auth-username": email.split("@", 1)[0],
        "x-tryops-auth-display-name": name,
        "x-tryops-auth-display-name-utf8": quote(name, safe=""),
        "x-tryops-auth-role": "account_member",
        "x-tryops-auth-scopes": scopes or "session:read account:read workload:run",
    }


@unittest.skipIf(TestClient is None or create_app is None, "FastAPI test client unavailable")
class AccountApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "tryops.db"
        self.original_connect = db.connect
        self._env_patch = patch.dict(os.environ, {"TRYOPS_QUOTA_GATEWAY_URL": ""}, clear=False)
        self._env_patch.start()
        self._connect_patch = patch.object(db, "connect", side_effect=lambda *_args, **_kwargs: self.original_connect(self.path))
        self._connect_patch.start()
        db.init_db(self.path)
        reset_quota_usage()
        reset_job_queue()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self._connect_patch.stop()
        self._env_patch.stop()
        self._tmp.cleanup()
        reset_job_queue()
        reset_quota_usage()

    def test_bootstrap_is_idempotent_per_subject(self) -> None:
        headers = auth_headers("kc-user-1", email="owner@example.com")

        first = self.client.post("/api/accounts/bootstrap", headers=headers).json()["data"]
        second = self.client.post("/api/accounts/bootstrap", headers=headers).json()["data"]

        self.assertEqual(first["account"]["id"], second["account"]["id"])
        conn = self.original_connect(self.path)
        try:
            members = db.get_account_members(conn, first["account"]["id"])
            self.assertEqual(len(members), 1)
            self.assertEqual(members[0]["role"], "account_owner")
        finally:
            conn.close()

    def test_bootstrap_preserves_utf8_display_name_from_gateway_header(self) -> None:
        headers = auth_headers("kc-user-utf8", email="utf8@example.com", display_name="Nguyễn Trung")

        session = self.client.post("/api/accounts/bootstrap", headers=headers).json()["data"]

        self.assertEqual(session["membership"]["display_name"], "Nguyễn Trung")
        self.assertEqual(session["account"]["name"], "Nguyễn Trung's Workspace")

    def test_account_jobs_includes_live_queue_records_without_persisted_snapshot(self) -> None:
        headers = auth_headers("kc-user-live-job", email="live-job@example.com")
        account = self.client.post("/api/accounts/bootstrap", headers=headers).json()["data"]["account"]
        release = Event()

        def runner(payload: dict[str, object]) -> dict[str, object]:
            release.wait(5)
            return {"status": "completed", "request_id": payload["request_id"]}

        accepted = VTON_JOB_QUEUE.submit(
            workload="vton",
            request_id="req-live-account-job",
            payload={"request_id": "req-live-account-job"},
            runner=runner,
            account_id=account["id"],
            active_limit=10,
        )
        try:
            response = self.client.get("/api/account/jobs?status=active&limit=20", headers=headers).json()
            job_ids = {job["job_id"] for job in response["data"]}

            self.assertIn(accepted["job_id"], job_ids)
            self.assertEqual(response["concurrency"]["active"], 1)
        finally:
            release.set()

    def test_account_dashboard_is_scoped_to_authenticated_account(self) -> None:
        first = self.client.post("/api/accounts/bootstrap", headers=auth_headers("kc-user-1", email="a@example.com")).json()["data"]
        second = self.client.post("/api/accounts/bootstrap", headers=auth_headers("kc-user-2", email="b@example.com")).json()["data"]
        conn = self.original_connect(self.path)
        try:
            db.insert_request(conn, {"kind": "vton", "account_id": first["account"]["id"], "status": "completed"})
            db.insert_request(conn, {"kind": "vton", "account_id": second["account"]["id"], "status": "completed"})
        finally:
            conn.close()

        dashboard = self.client.get("/api/account/dashboard", headers=auth_headers("kc-user-1", email="a@example.com")).json()["data"]

        self.assertEqual(dashboard["account"]["id"], first["account"]["id"])
        self.assertEqual(dashboard["usage"]["total_requests"], 1)
        self.assertEqual(dashboard["recent_requests"][0]["account_id"], first["account"]["id"])

    def test_authenticated_quota_uses_account_plan_not_client_payload(self) -> None:
        session = self.client.post("/api/accounts/bootstrap", headers=auth_headers("kc-user-1", email="a@example.com")).json()["data"]

        with patch("tryops.api.generate_openai_compatible_response", side_effect=_fake_real_llm_response):
            response = self.client.post(
                "/api/llm/generate",
                headers=auth_headers("kc-user-1", email="a@example.com"),
                json={
                    "prompt": "Say hello in one sentence.",
                    "model_alias": "champion",
                    "max_tokens": 8,
                    "structured": False,
                    "routing_mode": "direct",
                    "canary_percent": 0,
                    "shadow": False,
                    "optimized_available": False,
                    "fallback_enabled": False,
                    "semantic_cache_enabled": False,
                    "user_id": "attacker-user",
                    "quota_plan": "enterprise",
                },
            ).json()

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["account"]["id"], session["account"]["id"])
        self.assertEqual(response["quota"]["plan"], "free")
        self.assertEqual(response["quota"]["user_hash"], user_hash(session["account"]["id"]))

    def test_user_can_join_and_switch_between_workspaces(self) -> None:
        owner_headers = auth_headers("kc-owner", email="owner@example.com")
        member_headers = auth_headers("kc-member", email="member@example.com")
        owner = self.client.post("/api/accounts/bootstrap", headers=owner_headers).json()["data"]
        created = self.client.post(
            "/api/accounts",
            headers=owner_headers,
            json={"name": "Campaign Workspace", "description": "Shared styling"},
        ).json()["data"]
        self.client.post("/api/accounts/bootstrap", headers=member_headers)

        invite = self.client.post(
            f"/api/accounts/{created['account']['id']}/invitations",
            headers=owner_headers,
            json={"email": "member@example.com", "role": "account_member"},
        ).json()["data"]
        self.assertEqual(invite["status"], "accepted")

        accounts = self.client.get("/api/accounts", headers=member_headers).json()["data"]
        account_ids = {item["account"]["id"] for item in accounts}
        self.assertIn(created["account"]["id"], account_ids)
        self.assertNotEqual(owner["account"]["id"], created["account"]["id"])

        conn = self.original_connect(self.path)
        try:
            db.insert_request(conn, {"kind": "vton", "account_id": created["account"]["id"], "status": "completed"})
        finally:
            conn.close()

        dashboard = self.client.get(
            "/api/account/dashboard",
            headers={**member_headers, "x-tryops-account-id": created["account"]["id"]},
        ).json()["data"]
        self.assertEqual(dashboard["account"]["id"], created["account"]["id"])
        self.assertEqual(dashboard["usage"]["total_requests"], 1)

    def test_pending_invite_activates_on_first_login(self) -> None:
        owner_headers = auth_headers("kc-owner", email="owner@example.com")
        owner = self.client.post("/api/accounts/bootstrap", headers=owner_headers).json()["data"]

        pending = self.client.post(
            f"/api/accounts/{owner['account']['id']}/invitations",
            headers=owner_headers,
            json={"email": "new-user@example.com", "role": "account_viewer"},
        ).json()["data"]
        self.assertEqual(pending["status"], "pending")

        newcomer = self.client.post(
            "/api/accounts/bootstrap",
            headers=auth_headers("kc-new", email="new-user@example.com"),
        ).json()["data"]
        self.assertEqual(newcomer["account"]["id"], owner["account"]["id"])
        self.assertEqual(newcomer["membership"]["role"], "account_viewer")

    def test_inviting_existing_member_does_not_demote_owner(self) -> None:
        owner_headers = auth_headers("kc-owner", email="owner@example.com")
        owner = self.client.post("/api/accounts/bootstrap", headers=owner_headers).json()["data"]

        response = self.client.post(
            f"/api/accounts/{owner['account']['id']}/invitations",
            headers=owner_headers,
            json={"email": "owner@example.com", "role": "account_member"},
        ).json()

        self.assertEqual(response["status"], "rejected")
        self.assertEqual(response["error"]["code"], "invalid_invitation")
        members = self.client.get("/api/account/members", headers=owner_headers).json()["data"]
        self.assertEqual(members[0]["role"], "account_owner")

    def test_non_member_cannot_select_another_workspace(self) -> None:
        first = self.client.post("/api/accounts/bootstrap", headers=auth_headers("kc-a", email="a@example.com")).json()["data"]
        self.client.post("/api/accounts/bootstrap", headers=auth_headers("kc-b", email="b@example.com"))

        response = self.client.get(
            "/api/account/dashboard",
            headers={**auth_headers("kc-b", email="b@example.com"), "x-tryops-account-id": first["account"]["id"]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "account_forbidden")

    def test_viewer_member_cannot_run_workloads(self) -> None:
        owner_headers = auth_headers("kc-owner", email="owner@example.com")
        viewer_headers = auth_headers("kc-viewer", email="viewer@example.com")
        owner = self.client.post("/api/accounts/bootstrap", headers=owner_headers).json()["data"]
        self.client.post("/api/accounts/bootstrap", headers=viewer_headers)
        self.client.post(
            f"/api/accounts/{owner['account']['id']}/invitations",
            headers=owner_headers,
            json={"email": "viewer@example.com", "role": "account_viewer"},
        )

        response = self.client.post(
            "/api/llm/generate",
            headers={**viewer_headers, "x-tryops-account-id": owner["account"]["id"]},
            json={
                "prompt": "Say hello in one sentence.",
                "model_alias": "champion",
                "max_tokens": 8,
                "structured": False,
                "routing_mode": "direct",
                "canary_percent": 0,
                "shadow": False,
                "optimized_available": False,
                "fallback_enabled": False,
                "semantic_cache_enabled": False,
                "user_id": "spoof",
                "quota_plan": "enterprise",
            },
        ).json()

        self.assertEqual(response["status"], "rejected")
        self.assertEqual(response["error"]["details"][0]["message"], "missing_workload_member_role")


if __name__ == "__main__":
    unittest.main()
