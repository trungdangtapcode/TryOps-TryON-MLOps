from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any


SUPPORTED_QUOTA_PLANS = {"free", "team", "enterprise"}


PLAN_LIMITS = {
    "free": {
        "llm_requests_per_day": 20,
        "llm_tokens_per_day": 5_000,
        "vton_requests_per_day": 5,
    },
    "team": {
        "llm_requests_per_day": 500,
        "llm_tokens_per_day": 250_000,
        "vton_requests_per_day": 100,
    },
    "enterprise": {
        "llm_requests_per_day": 50_000,
        "llm_tokens_per_day": 25_000_000,
        "vton_requests_per_day": 10_000,
    },
}


@dataclass(frozen=True)
class QuotaRequest:
    user_id: str
    plan: str
    workload: str
    request_units: int = 1
    estimated_tokens: int = 0


class UsageQuotaLedger:
    def __init__(self) -> None:
        self._usage: dict[tuple[str, str, str], int] = defaultdict(int)

    def check_and_record(
        self,
        request: QuotaRequest,
        *,
        now: datetime | None = None,
        record: bool = True,
    ) -> dict[str, Any]:
        if request.plan not in SUPPORTED_QUOTA_PLANS:
            raise ValueError(f"unsupported quota plan '{request.plan}'")
        if request.workload not in {"llm", "vton"}:
            raise ValueError(f"unsupported quota workload '{request.workload}'")
        if request.request_units < 0 or request.estimated_tokens < 0:
            raise ValueError("quota usage values must be non-negative")

        period = _period_key(now or datetime.now(UTC))
        dimensions = _usage_dimensions(request)
        checks = []
        for dimension, increment in dimensions.items():
            key = (period, _user_hash(request.user_id), dimension)
            limit = int(PLAN_LIMITS[request.plan][dimension])
            used = self._usage[key]
            checks.append(
                {
                    "dimension": dimension,
                    "limit": limit,
                    "used": used,
                    "increment": increment,
                    "remaining_before": max(0, limit - used),
                    "allowed": used + increment <= limit,
                }
            )

        allowed = all(check["allowed"] for check in checks)
        if allowed and record:
            for check in checks:
                key = (period, _user_hash(request.user_id), str(check["dimension"]))
                self._usage[key] += int(check["increment"])

        return {
            "schema_version": "tryops.quota_decision.v1",
            "allowed": allowed,
            "period": period,
            "user_hash": _user_hash(request.user_id),
            "plan": request.plan,
            "workload": request.workload,
            "checks": [
                {
                    **check,
                    "used_after": check["used"] + check["increment"] if allowed and record else check["used"],
                    "remaining_after": (
                        max(0, check["limit"] - check["used"] - check["increment"])
                        if allowed and record
                        else max(0, check["limit"] - check["used"])
                    ),
                }
                for check in checks
            ],
            "recorded": bool(allowed and record),
            "reason": "within_quota" if allowed else "quota_exceeded",
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "tryops.quota_snapshot.v1",
            "usage": [
                {
                    "period": period,
                    "user_hash": user_hash,
                    "dimension": dimension,
                    "used": used,
                }
                for (period, user_hash, dimension), used in sorted(self._usage.items())
            ],
        }

    def reset(self) -> None:
        self._usage.clear()


GLOBAL_QUOTA_LEDGER = UsageQuotaLedger()


def check_and_record_quota(
    *,
    user_id: str,
    plan: str,
    workload: str,
    request_units: int = 1,
    estimated_tokens: int = 0,
    record: bool = True,
) -> dict[str, Any]:
    if record:
        gateway_decision = _check_gateway_quota(
            user_id=user_id,
            plan=plan,
            workload=workload,
            request_units=request_units,
            estimated_tokens=estimated_tokens,
        )
        if gateway_decision is not None:
            gateway_decision.setdefault("recorded", bool(gateway_decision.get("allowed")))
            return gateway_decision
    return GLOBAL_QUOTA_LEDGER.check_and_record(
        QuotaRequest(
            user_id=user_id,
            plan=plan,
            workload=workload,
            request_units=request_units,
            estimated_tokens=estimated_tokens,
        ),
        record=record,
    )


def reset_quota_usage() -> None:
    GLOBAL_QUOTA_LEDGER.reset()


def quota_snapshot() -> dict[str, Any]:
    return GLOBAL_QUOTA_LEDGER.snapshot()


def user_hash(user_id: str) -> str:
    return _user_hash(user_id)


def _usage_dimensions(request: QuotaRequest) -> dict[str, int]:
    if request.workload == "llm":
        return {
            "llm_requests_per_day": request.request_units,
            "llm_tokens_per_day": request.estimated_tokens,
        }
    return {"vton_requests_per_day": request.request_units}


def _period_key(now: datetime) -> str:
    return now.astimezone(UTC).date().isoformat()


def _user_hash(user_id: str) -> str:
    normalized = str(user_id).strip() or "anonymous"
    return sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _check_gateway_quota(
    *,
    user_id: str,
    plan: str,
    workload: str,
    request_units: int,
    estimated_tokens: int,
) -> dict[str, Any] | None:
    base_url = os.getenv("TRYOPS_QUOTA_GATEWAY_URL", "").strip().rstrip("/")
    if not base_url:
        return None
    payload = {
        "user_id": user_id,
        "plan": plan,
        "workload": workload,
        "request_units": request_units,
        "estimated_tokens": estimated_tokens,
    }
    request = urllib.request.Request(
        f"{base_url}/v1/quota/check",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = float(os.getenv("TRYOPS_QUOTA_GATEWAY_TIMEOUT_SECONDS", "0.5"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decision = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, ValueError, urllib.error.URLError):
        return None
    if isinstance(decision, dict) and decision.get("schema_version") == "tryops.quota_decision.v1":
        return decision
    return None
