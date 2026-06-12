from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tryops.quota import PLAN_LIMITS, quota_snapshot

DEFAULT_QUOTA_READ_MODEL_PATH = Path("artifacts/eval/quota/native_quota_read_model.json")

UNIT_PRICES_USD = {
    "llm_requests_per_day": 0.0001,
    "llm_tokens_per_day": 0.0000002,
    "vton_requests_per_day": 0.0125,
}


def load_quota_read_model(path: str | Path | None = None) -> dict[str, Any]:
    configured = path or os.getenv("TRYOPS_QUOTA_READ_MODEL_PATH", "").strip() or DEFAULT_QUOTA_READ_MODEL_PATH
    source = Path(configured)
    if source.exists():
        report = json.loads(source.read_text(encoding="utf-8"))
        if report.get("schema_version") == "tryops.native_quota_read_model.v1":
            report.setdefault("source", "native_go_artifact")
            return report

    snapshot = _gateway_quota_snapshot() or quota_snapshot()
    report = build_quota_read_model(snapshot=snapshot, source_path="live_or_local_snapshot")
    report["source"] = "gateway_snapshot" if snapshot.get("engine") == "native_rust_gateway" else "python_fallback_snapshot"
    return report


def build_quota_read_model(*, snapshot: dict[str, Any], source_path: str = "runtime") -> dict[str, Any]:
    rows = snapshot.get("usage", []) if isinstance(snapshot.get("usage"), list) else []
    grouped: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        period = str(row.get("period", "unknown"))
        user_hash = str(row.get("user_hash", "unknown"))
        dimension = str(row.get("dimension", "unknown"))
        key = (period, user_hash)
        grouped.setdefault(key, {})
        grouped[key][dimension] = grouped[key].get(dimension, 0) + int(row.get("used", 0) or 0)

    tenants = []
    for (period, user_hash), dimensions in sorted(grouped.items()):
        tenants.append(_tenant_model(period=period, user_hash=user_hash, plan="free", dimensions=dimensions))

    periods: dict[str, dict[str, Any]] = {}
    for tenant in tenants:
        period = tenant["period"]
        periods.setdefault(period, {"period": period, "tenants": 0, "total_used": 0, "showback_usd": 0.0})
        periods[period]["tenants"] += 1
        periods[period]["total_used"] += tenant["total_used"]
        periods[period]["showback_usd"] = round(periods[period]["showback_usd"] + tenant["showback_usd"], 6)

    summary = {
        "tenants": len(tenants),
        "periods": len(periods),
        "dimensions": len({item["dimension"] for tenant in tenants for item in tenant["dimensions"]}),
        "total_used": sum(int(tenant["total_used"]) for tenant in tenants),
        "total_limit": sum(int(tenant["total_limit"]) for tenant in tenants),
        "showback_usd": round(sum(float(tenant["showback_usd"]) for tenant in tenants), 6),
        "native_source": snapshot.get("engine") == "native_rust_gateway",
        "at_risk_tenants": sum(1 for tenant in tenants if tenant["risk"] in {"high", "exhausted"}),
    }
    checks = {
        "tenant_read_model_present": bool(tenants),
        "hashed_tenant_only": _hashed_only(rows),
        "showback_present": summary["showback_usd"] >= 0,
        "limits_present": summary["total_limit"] > 0 if tenants else True,
    }
    return {
        "schema_version": "tryops.native_quota_read_model.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": all(checks.values()),
        "coverage_level": "bff_runtime_quota_read_model",
        "source_path": source_path,
        "source_engine": str(snapshot.get("engine", "python_fallback")),
        "summary": summary,
        "periods": sorted(periods.values(), key=lambda item: item["period"]),
        "tenants": tenants,
        "checks": checks,
    }


def _tenant_model(*, period: str, user_hash: str, plan: str, dimensions: dict[str, int]) -> dict[str, Any]:
    items = []
    total_used = 0
    total_limit = 0
    showback = 0.0
    for dimension, used in sorted(dimensions.items()):
        limit = int(PLAN_LIMITS.get(plan, {}).get(dimension, 0))
        remaining = max(0, limit - used)
        price = UNIT_PRICES_USD.get(dimension, 0.0)
        item_showback = round(used * price, 6)
        items.append(
            {
                "dimension": dimension,
                "used": used,
                "limit": limit,
                "remaining": remaining,
                "utilization_pct": _utilization(used, limit),
                "unit_price_usd": price,
                "showback_usd": item_showback,
            }
        )
        total_used += used
        total_limit += limit
        showback += item_showback
    utilization = _utilization(total_used, total_limit)
    return {
        "period": period,
        "user_hash": user_hash,
        "plan": plan,
        "total_used": total_used,
        "total_limit": total_limit,
        "remaining": max(0, total_limit - total_used),
        "utilization_pct": utilization,
        "showback_usd": round(showback, 6),
        "dimensions": items,
        "risk": _risk(utilization),
    }


def _gateway_quota_snapshot() -> dict[str, Any] | None:
    base_url = os.getenv("TRYOPS_QUOTA_GATEWAY_URL", "").strip().rstrip("/")
    if not base_url:
        return None
    timeout = float(os.getenv("TRYOPS_QUOTA_GATEWAY_TIMEOUT_SECONDS", "0.5"))
    try:
        with urllib.request.urlopen(f"{base_url}/v1/quota/snapshot", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, ValueError, urllib.error.URLError):
        return None
    if isinstance(payload, dict) and payload.get("schema_version") == "tryops.quota_snapshot.v1":
        return payload
    return None


def _utilization(used: int, limit: int) -> float:
    if limit <= 0:
        return 0.0
    return round((used * 100.0) / limit, 2)


def _risk(utilization_pct: float) -> str:
    if utilization_pct >= 100:
        return "exhausted"
    if utilization_pct >= 80:
        return "high"
    if utilization_pct >= 50:
        return "medium"
    return "low"


def _hashed_only(rows: list[Any]) -> bool:
    for row in rows:
        if not isinstance(row, dict):
            continue
        user_hash = str(row.get("user_hash", ""))
        if "@" in user_hash or user_hash.startswith("user-") or user_hash == str(row.get("user_id", "")):
            return False
    return True
