from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


DEFAULT_API_KEYS_PATH = Path("configs/api_keys.json")
AUTH_DECISION_SCHEMA = "tryops.auth_decision.v1"
AUTH_REPORT_SCHEMA = "tryops.api_key_auth_report.v1"
SESSION_SCHEMA = "tryops.rbac_session.v1"
REQUIRED_ADMIN_SCOPES = {
    "promotion:evaluate",
    "lineage:create",
    "lineage:read",
    "admin:read",
    "session:read",
    "account:read",
    "account:write",
    "workload:run",
}
REQUIRED_RBAC_ROLES = {"viewer", "operator", "admin"}
FORBIDDEN_SECRET_FIELDS = {"api_key", "raw_key", "secret", "token", "password"}
PUBLIC_NAV_ITEMS = ("vton",)
SCOPE_NAV_ITEMS = {
    "account:read": ("account", "llm", "vton"),
    "admin:read": ("dashboard", "history", "runs", "registry", "evaluations", "experiments"),
    "lineage:read": ("governance",),
    "promotion:evaluate": ("incidents",),
}


def hash_api_key(api_key: str) -> str:
    normalized = str(api_key).strip()
    return sha256(normalized.encode("utf-8")).hexdigest()


def load_api_key_registry(path: str | Path = DEFAULT_API_KEYS_PATH) -> dict[str, Any]:
    registry = json.loads(Path(path).read_text(encoding="utf-8"))
    registry["keys"] = [_normalize_key_entry(entry) for entry in registry.get("keys", [])]
    return registry


def authenticate_api_key(
    api_key: object,
    *,
    required_scope: str,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(api_key, str) or not api_key.strip():
        return _auth_decision(
            allowed=False,
            required_scope=required_scope,
            reason="missing_api_key",
            principal=None,
        )

    registry = registry or load_api_key_registry()
    key_hash = hash_api_key(api_key)
    entry = _find_active_key_by_hash(registry, key_hash)
    if entry is None:
        return _auth_decision(
            allowed=False,
            required_scope=required_scope,
            reason="invalid_api_key",
            principal=None,
        )

    principal = _principal_from_entry(entry)
    if required_scope not in principal["scopes"]:
        return _auth_decision(
            allowed=False,
            required_scope=required_scope,
            reason="missing_scope",
            principal=principal,
        )

    return _auth_decision(
        allowed=True,
        required_scope=required_scope,
        reason="authorized",
        principal=principal,
    )


def authorize_admin_payload(payload: dict[str, Any], *, required_scope: str) -> dict[str, Any]:
    return authenticate_api_key(payload.get("api_key"), required_scope=required_scope)


def redact_admin_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    if "api_key" in redacted:
        redacted["api_key"] = "<redacted>"
    return redacted


def audit_api_key_registry(
    registry: dict[str, Any],
    *,
    required_scopes: set[str] | None = None,
) -> dict[str, Any]:
    required_scopes = required_scopes or REQUIRED_ADMIN_SCOPES
    keys = [_normalize_key_entry(entry) for entry in registry.get("keys", [])]
    key_ids = [entry["key_id"] for entry in keys]
    hashes = [entry["key_hash_sha256"] for entry in keys]
    active_scopes = sorted({scope for entry in keys if entry["active"] for scope in entry["scopes"]})
    active_roles = sorted({entry["role"] for entry in keys if entry["active"]})
    forbidden_fields = sorted(
        {
            field
            for entry in registry.get("keys", [])
            for field in entry
            if str(field).lower() in FORBIDDEN_SECRET_FIELDS
        }
    )
    duplicate_key_ids = sorted({key_id for key_id in key_ids if key_ids.count(key_id) > 1})
    duplicate_hashes = sorted({key_hash for key_hash in hashes if hashes.count(key_hash) > 1})
    invalid_hash_ids = sorted(
        entry["key_id"]
        for entry in keys
        if len(entry["key_hash_sha256"]) != 64
        or any(char not in "0123456789abcdef" for char in entry["key_hash_sha256"])
    )
    missing_required_scopes = sorted(required_scopes - set(active_scopes))
    missing_required_roles = sorted(REQUIRED_RBAC_ROLES - set(active_roles))
    passed = (
        bool(keys)
        and not forbidden_fields
        and not duplicate_key_ids
        and not duplicate_hashes
        and not invalid_hash_ids
        and not missing_required_scopes
        and not missing_required_roles
    )
    return {
        "schema_version": "tryops.api_key_registry_audit.v1",
        "key_count": len(keys),
        "active_key_count": sum(1 for entry in keys if entry["active"]),
        "roles": sorted({entry["role"] for entry in keys}),
        "required_roles": sorted(REQUIRED_RBAC_ROLES),
        "missing_required_roles": missing_required_roles,
        "active_scopes": active_scopes,
        "required_scopes": sorted(required_scopes),
        "missing_required_scopes": missing_required_scopes,
        "forbidden_secret_fields": forbidden_fields,
        "duplicate_key_ids": duplicate_key_ids,
        "duplicate_hashes": duplicate_hashes,
        "invalid_hash_key_ids": invalid_hash_ids,
        "passed": passed,
    }


def build_api_key_auth_report(
    *,
    scenarios: list[dict[str, Any]],
    registry_path: str | Path = DEFAULT_API_KEYS_PATH,
) -> dict[str, Any]:
    registry = load_api_key_registry(registry_path)
    registry_audit = audit_api_key_registry(registry)
    evaluated = []
    for scenario in scenarios:
        decision = authenticate_api_key(
            scenario.get("api_key"),
            required_scope=str(scenario["required_scope"]),
            registry=registry,
        )
        evaluated.append(
            {
                "name": str(scenario["name"]),
                "key_label": str(scenario.get("key_label", scenario["name"])),
                "required_scope": str(scenario["required_scope"]),
                "expected_allowed": bool(scenario["expected_allowed"]),
                "actual_allowed": bool(decision["allowed"]),
                "reason": decision["reason"],
                "principal": decision["principal"],
                "passed": bool(decision["allowed"]) == bool(scenario["expected_allowed"]),
            }
        )
    return {
        "schema_version": AUTH_REPORT_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "registry_path": str(registry_path),
        "registry_audit": registry_audit,
        "scenarios": evaluated,
        "passed": registry_audit["passed"] and all(item["passed"] for item in evaluated),
    }


def write_api_key_auth_report(
    *,
    scenarios: list[dict[str, Any]],
    output_path: str | Path,
    registry_path: str | Path = DEFAULT_API_KEYS_PATH,
) -> dict[str, Any]:
    report = build_api_key_auth_report(scenarios=scenarios, registry_path=registry_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def build_rbac_session(
    principal: dict[str, Any],
    *,
    account: dict[str, Any] | None = None,
    membership: dict[str, Any] | None = None,
    accounts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scopes = sorted({str(scope) for scope in principal.get("scopes", [])})
    scope_set = set(scopes)
    membership_role = str((membership or {}).get("role") or "")
    is_platform_admin = "admin:read" in scope_set or str(principal.get("role")) == "platform_admin"
    can_read_account = "account:read" in scope_set and membership_role in {
        "account_owner",
        "account_member",
        "account_viewer",
    }
    can_run_workload = (
        "workload:run" in scope_set
        and membership_role in {"account_owner", "account_member"}
    ) or is_platform_admin
    can_manage_account = membership_role == "account_owner" or is_platform_admin
    nav_items = list(PUBLIC_NAV_ITEMS)
    for scope, items in SCOPE_NAV_ITEMS.items():
        if scope in scope_set:
            nav_items.extend(items)
    if not can_read_account and "account" in nav_items:
        nav_items.remove("account")
    if not can_run_workload and "llm" in nav_items:
        nav_items.remove("llm")
    nav_items = sorted(set(nav_items), key=_nav_order)
    return {
        "schema_version": SESSION_SCHEMA,
        "principal": {
            "key_id": str(principal.get("key_id", "")),
            "subject": str(principal.get("subject") or principal.get("key_id", "")),
            "email": str(principal.get("email") or ""),
            "username": str(principal.get("username") or ""),
            "display_name": str(principal.get("display_name") or ""),
            "provider": str(principal.get("provider") or "api_key"),
            "role": str(principal.get("role", "")),
            "scopes": scopes,
        },
        "account": account,
        "active_account": account,
        "accounts": accounts or ([] if account is None else [{"account": account, "membership": membership}]),
        "membership": membership,
        "permissions": {
            "nav": nav_items,
            "can_read_account": can_read_account or is_platform_admin,
            "can_manage_account": can_manage_account,
            "can_run_workload": can_run_workload,
            "can_read_admin": is_platform_admin,
            "can_read_lineage": "lineage:read" in scope_set,
            "can_create_lineage": "lineage:create" in scope_set,
            "can_promote": "promotion:evaluate" in scope_set,
        },
    }


def _normalize_key_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "key_id": str(entry.get("key_id", "")),
        "role": str(entry.get("role", "")),
        "key_hash_sha256": str(entry.get("key_hash_sha256", "")).lower(),
        "scopes": sorted({str(scope) for scope in entry.get("scopes", [])}),
        "active": bool(entry.get("active", True)),
    }


def _find_active_key_by_hash(registry: dict[str, Any], key_hash: str) -> dict[str, Any] | None:
    for entry in registry.get("keys", []):
        normalized = _normalize_key_entry(entry)
        if normalized["active"] and normalized["key_hash_sha256"] == key_hash:
            return normalized
    return None


def _principal_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "key_id": str(entry["key_id"]),
        "subject": str(entry["key_id"]),
        "provider": "api_key",
        "email": "",
        "username": str(entry["key_id"]),
        "display_name": str(entry["key_id"]),
        "role": str(entry["role"]),
        "scopes": list(entry["scopes"]),
    }


def _auth_decision(
    *,
    allowed: bool,
    required_scope: str,
    reason: str,
    principal: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": AUTH_DECISION_SCHEMA,
        "allowed": allowed,
        "required_scope": required_scope,
        "reason": reason,
        "principal": principal,
    }


def _nav_order(item: str) -> int:
    order = {
        "dashboard": 0,
        "demo": 1,
        "llm": 2,
        "vton": 3,
        "history": 4,
        "runs": 5,
        "registry": 6,
        "evaluations": 7,
        "governance": 8,
        "incidents": 9,
    }
    return order.get(item, 100)
