from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.auth import (  # noqa: E402
    authenticate_api_key,
    build_api_key_auth_report,
    build_rbac_session,
    hash_api_key,
    load_api_key_registry,
    redact_admin_payload,
    write_api_key_auth_report,
)


class AuthTests(unittest.TestCase):
    def test_hash_api_key_matches_demo_registry_hash(self) -> None:
        registry = load_api_key_registry(ROOT / "configs/api_keys.json")
        admin = next(entry for entry in registry["keys"] if entry["key_id"] == "admin-demo")

        self.assertEqual(hash_api_key("tryops-admin-demo-key"), admin["key_hash_sha256"])
        self.assertNotIn("tryops-admin-demo-key", str(registry))

    def test_authenticate_api_key_enforces_required_scope(self) -> None:
        registry = load_api_key_registry(ROOT / "configs/api_keys.json")

        allowed = authenticate_api_key(
            "tryops-risk-demo-key",
            required_scope="promotion:evaluate",
            registry=registry,
        )
        denied = authenticate_api_key(
            "tryops-risk-demo-key",
            required_scope="lineage:create",
            registry=registry,
        )

        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["principal"]["role"], "risk_reviewer")
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["reason"], "missing_scope")
        self.assertNotIn("tryops-risk-demo-key", str(allowed))

    def test_rbac_session_exposes_role_nav_permissions(self) -> None:
        registry = load_api_key_registry(ROOT / "configs/api_keys.json")
        viewer = authenticate_api_key(
            "tryops-viewer-demo-key",
            required_scope="session:read",
            registry=registry,
        )
        operator = authenticate_api_key(
            "tryops-operator-demo-key",
            required_scope="session:read",
            registry=registry,
        )
        admin = authenticate_api_key(
            "tryops-admin-demo-key",
            required_scope="session:read",
            registry=registry,
        )

        viewer_session = build_rbac_session(viewer["principal"])
        operator_session = build_rbac_session(operator["principal"])
        admin_session = build_rbac_session(admin["principal"])

        self.assertEqual(viewer_session["principal"]["role"], "viewer")
        self.assertIn("dashboard", viewer_session["permissions"]["nav"])
        self.assertNotIn("incidents", viewer_session["permissions"]["nav"])
        self.assertEqual(operator_session["principal"]["role"], "operator")
        self.assertIn("incidents", operator_session["permissions"]["nav"])
        self.assertFalse(operator_session["permissions"]["can_create_lineage"])
        self.assertTrue(admin_session["permissions"]["can_create_lineage"])

    def test_account_owner_membership_can_manage_without_write_scope(self) -> None:
        session = build_rbac_session(
            {
                "key_id": "kc-owner",
                "subject": "kc-owner",
                "role": "account_member",
                "scopes": ["session:read", "account:read", "workload:run"],
            },
            account={
                "id": "acct_owner",
                "name": "Owner Workspace",
                "slug": "owner-workspace",
                "plan": "free",
                "status": "active",
                "created_at": "2026-06-13T00:00:00Z",
            },
            membership={
                "id": "member_owner",
                "account_id": "acct_owner",
                "subject": "kc-owner",
                "role": "account_owner",
                "status": "active",
                "created_at": "2026-06-13T00:00:00Z",
            },
        )

        self.assertTrue(session["permissions"]["can_manage_account"])

    def test_auth_report_is_redacted_and_passes(self) -> None:
        scenarios = [
            {
                "name": "admin_ok",
                "key_label": "admin-demo",
                "api_key": "tryops-admin-demo-key",
                "required_scope": "lineage:create",
                "expected_allowed": True,
            },
            {
                "name": "viewer_denied",
                "key_label": "viewer-demo",
                "api_key": "tryops-viewer-demo-key",
                "required_scope": "promotion:evaluate",
                "expected_allowed": False,
            },
        ]
        report = build_api_key_auth_report(
            scenarios=scenarios,
            registry_path=ROOT / "configs/api_keys.json",
        )

        self.assertTrue(report["passed"])
        self.assertNotIn("tryops-admin-demo-key", str(report))
        self.assertNotIn("tryops-viewer-demo-key", str(report))
        self.assertEqual(report["registry_audit"]["missing_required_scopes"], [])
        self.assertEqual(report["registry_audit"]["missing_required_roles"], [])

    def test_write_api_key_auth_report_creates_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "api_key_auth_report.json"

            report = write_api_key_auth_report(
                scenarios=[
                    {
                        "name": "missing_key",
                        "key_label": "missing",
                        "api_key": "",
                        "required_scope": "promotion:evaluate",
                        "expected_allowed": False,
                    }
                ],
                registry_path=ROOT / "configs/api_keys.json",
                output_path=output,
            )

            self.assertTrue(output.exists())
            self.assertTrue(report["passed"])
            self.assertIn("tryops.api_key_auth_report.v1", output.read_text(encoding="utf-8"))

    def test_redact_admin_payload_removes_raw_key_from_payload_copy(self) -> None:
        redacted = redact_admin_payload({"api_key": "tryops-admin-demo-key", "candidate": {"id": "demo"}})

        self.assertEqual(redacted["api_key"], "<redacted>")
        self.assertNotEqual(redacted["api_key"], "tryops-admin-demo-key")


if __name__ == "__main__":
    unittest.main()
