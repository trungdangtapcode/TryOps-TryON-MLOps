from __future__ import annotations

import json
import math
import os
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence


NATIVE_EXPERIMENT_ROUTER_SCHEMA = "tryops.native_experiment_router.v1"
DEFAULT_NATIVE_EXPERIMENT_ROUTER_CLI = Path("artifacts/native/tryops_experiment_router_cli")

DEFAULT_GUARDRAIL_THRESHOLDS = {
    "max_block_rate": 0.02,
    "max_latency_p95_ms": 500.0,
    "max_error_rate": 0.01,
}


def route_with_native_experiment_router(
    variants: Sequence[Mapping[str, Any]],
    *,
    mode: str,
    request_id: str,
    experiment_id: str = "tryops-online-experiment",
    holdback_percent: float = 0.0,
    guardrail_thresholds: Mapping[str, float] | None = None,
    holdback_alias: str = "champion",
    holdback_adapter: str = "openai-compatible-vllm",
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    """Route one request through the native experiment engine when available."""

    if mode not in {"ab", "bandit"}:
        raise ValueError("mode must be 'ab' or 'bandit'")
    if not request_id:
        raise ValueError("request_id is required")
    if not variants:
        raise ValueError("variants cannot be empty")

    thresholds = _thresholds(guardrail_thresholds)
    cli = Path(
        str(
            cli_path
            or os.environ.get("TRYOPS_NATIVE_EXPERIMENT_ROUTER_CLI", DEFAULT_NATIVE_EXPERIMENT_ROUTER_CLI)
        )
    )
    if cli.exists() and os.access(cli, os.X_OK):
        completed = subprocess.run(
            [str(cli)],
            input=_wire_payload(
                variants,
                mode=mode,
                request_id=request_id,
                experiment_id=experiment_id,
                holdback_percent=holdback_percent,
                thresholds=thresholds,
                holdback_alias=holdback_alias,
                holdback_adapter=holdback_adapter,
            ),
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            payload["available"] = payload.get("schema_version") == NATIVE_EXPERIMENT_ROUTER_SCHEMA
            payload["source"] = "native_cpp_cli"
            payload["returncode"] = completed.returncode
            payload["cli_path"] = str(cli)
            return payload
        return {
            "schema_version": NATIVE_EXPERIMENT_ROUTER_SCHEMA,
            "available": True,
            "source": "native_cpp_cli_error",
            "returncode": completed.returncode,
            "cli_path": str(cli),
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }

    fallback = _python_route(
        variants,
        mode=mode,
        request_id=request_id,
        experiment_id=experiment_id,
        holdback_percent=holdback_percent,
        guardrail_thresholds=thresholds,
        holdback_alias=holdback_alias,
        holdback_adapter=holdback_adapter,
    )
    fallback["available"] = False
    fallback["source"] = "python_deterministic_fallback"
    fallback["returncode"] = None
    fallback["cli_path"] = str(cli)
    return fallback


def _wire_payload(
    variants: Sequence[Mapping[str, Any]],
    *,
    mode: str,
    request_id: str,
    experiment_id: str,
    holdback_percent: float,
    thresholds: Mapping[str, float],
    holdback_alias: str,
    holdback_adapter: str,
) -> str:
    lines = [
        f"mode={mode}",
        f"request_id={request_id}",
        f"experiment_id={experiment_id}",
        f"holdback_percent={float(holdback_percent)}",
        f"holdback_alias={holdback_alias}",
        f"holdback_adapter={holdback_adapter}",
        f"guardrail.max_block_rate={thresholds['max_block_rate']}",
        f"guardrail.max_latency_p95_ms={thresholds['max_latency_p95_ms']}",
        f"guardrail.max_error_rate={thresholds['max_error_rate']}",
        f"variant_count={len(variants)}",
    ]
    fields = [
        "name",
        "adapter",
        "allocation_percent",
        "impressions",
        "rewards",
        "guardrail_block_rate",
        "latency_p95_ms",
        "error_rate",
    ]
    for idx, variant in enumerate(variants):
        for field in fields:
            if field in variant:
                lines.append(f"variant.{idx}.{field}={variant[field]}")
    return "\n".join(lines) + "\n"


def _python_route(
    variants: Sequence[Mapping[str, Any]],
    *,
    mode: str,
    request_id: str,
    experiment_id: str,
    holdback_percent: float,
    guardrail_thresholds: Mapping[str, float],
    holdback_alias: str,
    holdback_adapter: str,
) -> dict[str, Any]:
    holdback = min(max(float(holdback_percent), 0.0), 95.0)
    routed = [_prepare_variant(v, guardrail_thresholds) for v in variants]
    _assign_weights(routed, mode=mode, holdback_percent=holdback)
    bucket = _stable_percent_bucket(f"{experiment_id}::{request_id}")
    in_holdback = bucket < holdback
    routed_bucket = 0.0
    selected = {"variant": holdback_alias, "adapter": holdback_adapter, "reason": "holdback"}
    if not in_holdback:
        routed_bucket = bucket - holdback
        selected_variant = _choose_variant(routed, routed_bucket)
        if selected_variant is None:
            raise ValueError("no eligible variants after guardrail filtering")
        selected = {
            "variant": selected_variant["name"],
            "adapter": selected_variant["adapter"],
            "reason": "bandit_ucb_guarded" if mode == "bandit" else "ab_bucket_guarded",
        }

    return {
        "schema_version": NATIVE_EXPERIMENT_ROUTER_SCHEMA,
        "engine": {"name": "tryops_experiment_router", "language": "python", "version": "0.1.0"},
        "mode": mode,
        "experiment_id": experiment_id,
        "request_id": request_id,
        "bucket": round(bucket, 6),
        "routed_bucket": round(routed_bucket, 6),
        "holdback": in_holdback,
        "selected": selected,
        "guardrail_thresholds": dict(guardrail_thresholds),
        "variants": routed,
    }


def _prepare_variant(
    variant: Mapping[str, Any],
    thresholds: Mapping[str, float],
) -> dict[str, Any]:
    name = str(variant.get("name", "")).strip()
    if not name:
        raise ValueError("variant name is required")
    prepared = {
        "name": name,
        "adapter": str(variant.get("adapter") or name),
        "eligible": True,
        "violations": [],
        "ab_allocation_percent": float(variant.get("allocation_percent", 0.0)),
        "traffic_percent": 0.0,
        "impressions": float(variant.get("impressions", 0.0)),
        "rewards": float(variant.get("rewards", 0.0)),
        "reward_rate": 0.0,
        "ucb_score": 0.0,
        "guardrail_block_rate": float(variant.get("guardrail_block_rate", 0.0)),
        "latency_p95_ms": float(variant.get("latency_p95_ms", 0.0)),
        "error_rate": float(variant.get("error_rate", 0.0)),
    }
    if prepared["guardrail_block_rate"] > thresholds["max_block_rate"]:
        prepared["eligible"] = False
        prepared["violations"].append("guardrail_block_rate")
    if prepared["latency_p95_ms"] > thresholds["max_latency_p95_ms"]:
        prepared["eligible"] = False
        prepared["violations"].append("latency_p95_ms")
    if prepared["error_rate"] > thresholds["max_error_rate"]:
        prepared["eligible"] = False
        prepared["violations"].append("error_rate")
    if prepared["impressions"] > 0.0:
        prepared["reward_rate"] = prepared["rewards"] / prepared["impressions"]
    return prepared


def _assign_weights(
    variants: list[dict[str, Any]],
    *,
    mode: str,
    holdback_percent: float,
) -> None:
    eligible = [v for v in variants if v["eligible"]]
    if not eligible:
        raise ValueError("no eligible variants after guardrail filtering")
    total_weight = 0.0
    if mode == "ab":
        for variant in eligible:
            variant["_route_weight"] = max(0.0, variant["ab_allocation_percent"])
            total_weight += variant["_route_weight"]
        if total_weight <= 0.0:
            for variant in eligible:
                variant["_route_weight"] = 1.0
            total_weight = float(len(eligible))
    elif mode == "bandit":
        total_impressions = max(1.0, sum(max(0.0, v["impressions"]) for v in variants))
        for variant in eligible:
            if variant["impressions"] <= 0.0:
                variant["ucb_score"] = 2.0
            else:
                variant["ucb_score"] = variant["reward_rate"] + math.sqrt(
                    (2.0 * math.log(max(2.0, total_impressions))) / variant["impressions"]
                )
            variant["_route_weight"] = max(0.000001, variant["ucb_score"])
            total_weight += variant["_route_weight"]
    else:
        raise ValueError("mode must be 'ab' or 'bandit'")

    routed_percent = max(0.0, 100.0 - holdback_percent)
    for variant in variants:
        if variant["eligible"]:
            variant["traffic_percent"] = (variant["_route_weight"] / total_weight) * routed_percent
        variant.pop("_route_weight", None)


def _choose_variant(variants: Sequence[Mapping[str, Any]], routed_bucket: float) -> Mapping[str, Any] | None:
    cumulative = 0.0
    fallback = None
    for variant in variants:
        if not variant["eligible"]:
            continue
        fallback = variant
        cumulative += float(variant["traffic_percent"])
        if routed_bucket < cumulative:
            return variant
    return fallback


def _thresholds(values: Mapping[str, float] | None) -> dict[str, float]:
    merged = dict(DEFAULT_GUARDRAIL_THRESHOLDS)
    for key, value in (values or {}).items():
        if key in merged:
            merged[key] = float(value)
    return merged


def _stable_percent_bucket(value: str) -> float:
    digest = sha256(value.encode("utf-8")).hexdigest()
    integer = int(digest[:8], 16)
    return (integer / 0xFFFFFFFF) * 100.0
