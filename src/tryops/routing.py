from __future__ import annotations

from hashlib import sha256
from typing import Any

from tryops.native_experiment_router import route_with_native_experiment_router
from tryops.pipelines.llm_baseline import SUPPORTED_MODEL_ALIASES as SUPPORTED_LLM_ALIASES


SUPPORTED_VTON_ALIASES = {
    "baseline": "naive-overlay-vton",
    "champion": "naive-overlay-vton",
    "challenger": "naive-overlay-vton",
    "candidate": "naive-overlay-vton",
}


def resolve_model_alias(workload: str, model_alias: str) -> dict[str, str]:
    """Resolve a safe model alias to the local adapter name."""

    if workload == "llm":
        if model_alias not in SUPPORTED_LLM_ALIASES:
            raise ValueError(f"unsupported LLM alias '{model_alias}'")
        return {"workload": workload, "model_alias": model_alias, "adapter": "tryops-rule-baseline"}
    if workload == "vton":
        if model_alias not in SUPPORTED_VTON_ALIASES:
            raise ValueError(f"unsupported VTON alias '{model_alias}'")
        return {"workload": workload, "model_alias": model_alias, "adapter": SUPPORTED_VTON_ALIASES[model_alias]}
    raise ValueError(f"unsupported workload '{workload}'")


def build_routing_decision(
    *,
    workload: str,
    request_id: str,
    requested_alias: str,
    routing_mode: str = "direct",
    canary_percent: float = 0.0,
    shadow: bool = False,
    fallback_enabled: bool = False,
    fallback_alias: str = "baseline",
    route_health: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build deterministic champion/challenger routing metadata."""

    if routing_mode not in {"direct", "canary"}:
        raise ValueError("routing_mode must be 'direct' or 'canary'")
    if canary_percent < 0.0 or canary_percent > 100.0:
        raise ValueError("canary_percent must be between 0 and 100")

    primary_alias = requested_alias
    reason = "requested_alias"
    if routing_mode == "canary":
        canary_bucket = stable_percent_bucket(request_id)
        if canary_bucket < canary_percent:
            primary_alias = "challenger"
            reason = "canary_challenger"
        else:
            primary_alias = "champion"
            reason = "canary_champion"

    primary = resolve_model_alias(workload, primary_alias)
    decision: dict[str, Any] = {
        "mode": routing_mode,
        "requested_alias": requested_alias,
        "primary_alias": primary_alias,
        "primary_adapter": primary["adapter"],
        "reason": reason,
        "canary_percent": float(canary_percent),
        "bucket": stable_percent_bucket(request_id),
    }
    if shadow:
        shadow_alias = "challenger" if primary_alias != "challenger" else "champion"
        shadow_route = resolve_model_alias(workload, shadow_alias)
        decision["shadow_alias"] = shadow_alias
        decision["shadow_adapter"] = shadow_route["adapter"]
    if fallback_enabled:
        decision = apply_fallback_route(
            decision,
            workload=workload,
            fallback_alias=fallback_alias,
            route_health=route_health or {},
        )
    return decision


def build_experiment_routing_decision(
    *,
    workload: str,
    request_id: str,
    experiment_id: str,
    variants: list[dict[str, Any]],
    mode: str = "bandit",
    holdback_percent: float = 0.0,
    guardrail_thresholds: dict[str, float] | None = None,
    cli_path: str | None = None,
) -> dict[str, Any]:
    """Build an A/B or bandit routing decision over the supported model aliases."""

    experiment = route_with_native_experiment_router(
        variants,
        mode=mode,
        request_id=request_id,
        experiment_id=experiment_id,
        holdback_percent=holdback_percent,
        guardrail_thresholds=guardrail_thresholds,
        cli_path=cli_path,
    )
    if "selected" not in experiment:
        raise RuntimeError(f"experiment router failed: {experiment.get('error', 'unknown error')}")

    selected_alias = str(experiment["selected"]["variant"])
    primary = resolve_model_alias(workload, selected_alias)
    selected_adapter = str(experiment["selected"].get("adapter") or primary["adapter"])
    return {
        "mode": f"experiment_{mode}",
        "routing_mode": f"experiment_{mode}",
        "workload": workload,
        "request_id": request_id,
        "experiment_id": experiment_id,
        "requested_alias": selected_alias,
        "primary_alias": selected_alias,
        "primary_adapter": selected_adapter,
        "reason": experiment["selected"].get("reason", "experiment_route"),
        "bucket": experiment.get("bucket"),
        "experiment": experiment,
    }


def apply_fallback_route(
    decision: dict[str, Any],
    *,
    workload: str,
    fallback_alias: str,
    route_health: dict[str, str],
) -> dict[str, Any]:
    """Switch an unhealthy optimized LLM route back to the deterministic baseline."""

    if workload != "llm":
        return {
            **decision,
            "fallback": {
                "enabled": False,
                "applied": False,
                "reason": "fallback currently applies only to LLM routes",
            },
        }
    if fallback_alias != "baseline":
        raise ValueError("fallback_alias must be 'baseline' for the local LLM fallback policy")

    primary_alias = str(decision["primary_alias"])
    primary_status = route_health.get(primary_alias, "unknown")
    fallback_route = resolve_model_alias(workload, fallback_alias)
    fallback = {
        "enabled": True,
        "applied": False,
        "fallback_alias": fallback_alias,
        "fallback_adapter": fallback_route["adapter"],
        "primary_health_status": primary_status,
    }
    if primary_alias == fallback_alias:
        fallback["reason"] = "primary already uses baseline"
        return {**decision, "fallback": fallback}
    if _route_is_healthy(primary_status):
        fallback["reason"] = "primary route healthy"
        return {**decision, "fallback": fallback}

    updated = {
        **decision,
        "primary_alias": fallback_alias,
        "primary_adapter": fallback_route["adapter"],
        "pre_fallback_alias": primary_alias,
        "pre_fallback_adapter": decision["primary_adapter"],
        "reason": "fallback_to_baseline",
        "fallback": {
            **fallback,
            "applied": True,
            "reason": f"primary route status '{primary_status}' is not healthy",
        },
    }
    if "shadow_alias" in updated and updated["shadow_alias"] == fallback_alias:
        updated.pop("shadow_alias", None)
        updated.pop("shadow_adapter", None)
    return updated


def _route_is_healthy(status: str) -> bool:
    return str(status).strip().lower() in {"ready", "healthy", "available", "ok"}


def stable_percent_bucket(value: str) -> float:
    digest = sha256(value.encode("utf-8")).hexdigest()
    integer = int(digest[:8], 16)
    return round((integer / 0xFFFFFFFF) * 100.0, 6)
