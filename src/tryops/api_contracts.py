from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from tryops.pipelines.llm_baseline import SUPPORTED_MODEL_ALIASES
from tryops.experiments import (
    DEFAULT_EXPERIMENT_HOLDBACK_PERCENT,
    DEFAULT_EXPERIMENT_ID,
    normalize_experiment_variants,
    normalize_guardrail_thresholds,
)
from tryops.quota import SUPPORTED_QUOTA_PLANS
from tryops.routing import SUPPORTED_VTON_ALIASES


API_VERSION = "v1"
SUPPORTED_API_VERSIONS = ["v1"]
MAX_PROMPT_CHARS = 8000
MAX_IMAGE_BYTES = 10 * 1024 * 1024
DEFAULT_TIMEOUT_MS = 30_000
MAX_TIMEOUT_MS = 300_000
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def request_id_from_payload(payload: dict[str, Any]) -> str:
    request_id = str(payload.get("request_id", "")).strip()
    return request_id or f"req-{uuid4()}"


def structured_error(
    *,
    request_id: str,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    workload: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "api_version": API_VERSION,
        "request_id": request_id,
        "status": "rejected",
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        },
    }
    if workload is not None:
        response["workload"] = workload
    return response


def attach_response_metadata(
    response: dict[str, Any],
    *,
    request_id: str,
    workload: str,
    model_alias: str,
) -> dict[str, Any]:
    response["api_version"] = API_VERSION
    response["request_id"] = request_id
    response["workload"] = workload
    response["model_alias"] = model_alias
    return response


def readiness_state() -> dict[str, Any]:
    return {
        "api_version": API_VERSION,
        "status": "ready",
        "components": {
            "api": {"status": "ready"},
            "vton_baseline": {"status": "ready", "adapter": "naive-overlay-vton"},
            "llm_baseline": {"status": "ready", "adapter": "tryops-rule-baseline"},
            "registry": {"status": "degraded", "reason": "local file-backed registry only"},
            "rust_gateway": {
                "status": "ready",
                "reason": "Axum gateway builds, tests, smokes, and owns native quota admission",
            },
            "go_controller": {"status": "unverified", "reason": "go not installed in workspace"},
            "go_guardrail_sidecar": {
                "status": "configured" if "TRYOPS_GUARDRAIL_URL" in os.environ else "optional",
                "reason": "native HTTP sidecar is preferred when TRYOPS_GUARDRAIL_URL is set",
            },
        },
    }


def validate_llm_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append({"field": "prompt", "message": "prompt is required and must be a non-empty string"})
    elif len(prompt) > MAX_PROMPT_CHARS:
        errors.append({"field": "prompt", "message": f"prompt must be at most {MAX_PROMPT_CHARS} characters"})

    model_alias = str(payload.get("model_alias", "baseline"))
    if model_alias not in SUPPORTED_MODEL_ALIASES:
        errors.append({"field": "model_alias", "message": f"unsupported alias '{model_alias}'"})

    max_tokens = payload.get("max_tokens", 256)
    try:
        max_tokens_int = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens_int = 0
        errors.append({"field": "max_tokens", "message": "max_tokens must be an integer"})
    if max_tokens_int < 1 or max_tokens_int > 2048:
        errors.append({"field": "max_tokens", "message": "max_tokens must be between 1 and 2048"})

    structured = payload.get("structured", True)
    if not isinstance(structured, bool):
        errors.append({"field": "structured", "message": "structured must be a boolean"})

    routing_mode = str(payload.get("routing_mode", "direct"))
    if routing_mode not in {"direct", "canary", "experiment_ab", "experiment_bandit"}:
        errors.append(
            {
                "field": "routing_mode",
                "message": "routing_mode must be 'direct', 'canary', 'experiment_ab', or 'experiment_bandit'",
            }
        )

    canary_percent = payload.get("canary_percent", 0.0)
    try:
        canary_percent_float = float(canary_percent)
    except (TypeError, ValueError):
        canary_percent_float = -1.0
        errors.append({"field": "canary_percent", "message": "canary_percent must be numeric"})
    if canary_percent_float < 0.0 or canary_percent_float > 100.0:
        errors.append({"field": "canary_percent", "message": "canary_percent must be between 0 and 100"})

    shadow = payload.get("shadow", False)
    if not isinstance(shadow, bool):
        errors.append({"field": "shadow", "message": "shadow must be a boolean"})

    fallback_enabled = payload.get("fallback_enabled", False)
    if not isinstance(fallback_enabled, bool):
        errors.append({"field": "fallback_enabled", "message": "fallback_enabled must be a boolean"})

    optimized_available = payload.get("optimized_available", False)
    if not isinstance(optimized_available, bool):
        errors.append({"field": "optimized_available", "message": "optimized_available must be a boolean"})

    semantic_cache_enabled = payload.get("semantic_cache_enabled", True)
    if not isinstance(semantic_cache_enabled, bool):
        errors.append({"field": "semantic_cache_enabled", "message": "semantic_cache_enabled must be a boolean"})

    semantic_cache_threshold = payload.get("semantic_cache_threshold", 0.72)
    try:
        semantic_cache_threshold_float = float(semantic_cache_threshold)
    except (TypeError, ValueError):
        semantic_cache_threshold_float = -1.0
        errors.append({"field": "semantic_cache_threshold", "message": "semantic_cache_threshold must be numeric"})
    if semantic_cache_threshold_float < 0.0 or semantic_cache_threshold_float > 1.0:
        errors.append({"field": "semantic_cache_threshold", "message": "semantic_cache_threshold must be between 0 and 1"})

    user_id = str(payload.get("user_id", "anonymous")).strip() or "anonymous"
    if len(user_id) > 128:
        errors.append({"field": "user_id", "message": "user_id must be at most 128 characters"})

    quota_plan = str(payload.get("quota_plan", "free")).strip().lower() or "free"
    if quota_plan not in SUPPORTED_QUOTA_PLANS:
        errors.append({"field": "quota_plan", "message": f"quota_plan must be one of {sorted(SUPPORTED_QUOTA_PLANS)}"})

    timeout_ms_int = _validate_timeout_ms(payload, errors)
    experiment_id = str(payload.get("experiment_id", DEFAULT_EXPERIMENT_ID)).strip() or DEFAULT_EXPERIMENT_ID
    holdback_percent = payload.get("experiment_holdback_percent", DEFAULT_EXPERIMENT_HOLDBACK_PERCENT)
    try:
        holdback_percent_float = float(holdback_percent)
    except (TypeError, ValueError):
        holdback_percent_float = -1.0
        errors.append({"field": "experiment_holdback_percent", "message": "experiment_holdback_percent must be numeric"})
    if holdback_percent_float < 0.0 or holdback_percent_float > 95.0:
        errors.append({"field": "experiment_holdback_percent", "message": "experiment_holdback_percent must be between 0 and 95"})

    try:
        experiment_variants = normalize_experiment_variants(payload.get("experiment_variants"))
    except ValueError as exc:
        experiment_variants = []
        errors.append({"field": "experiment_variants", "message": str(exc)})
    try:
        experiment_guardrail_thresholds = normalize_guardrail_thresholds(payload.get("experiment_guardrail_thresholds"))
    except ValueError as exc:
        experiment_guardrail_thresholds = {}
        errors.append({"field": "experiment_guardrail_thresholds", "message": str(exc)})

    return (
        {
            "prompt": prompt if isinstance(prompt, str) else "",
            "model_alias": model_alias,
            "max_tokens": max_tokens_int,
            "structured": structured if isinstance(structured, bool) else True,
            "routing_mode": routing_mode,
            "canary_percent": canary_percent_float,
            "shadow": shadow if isinstance(shadow, bool) else False,
            "fallback_enabled": fallback_enabled if isinstance(fallback_enabled, bool) else False,
            "optimized_available": optimized_available if isinstance(optimized_available, bool) else False,
            "semantic_cache_enabled": semantic_cache_enabled if isinstance(semantic_cache_enabled, bool) else True,
            "semantic_cache_threshold": semantic_cache_threshold_float,
            "user_id": user_id,
            "quota_plan": quota_plan,
            "timeout_ms": timeout_ms_int,
            "experiment_id": experiment_id,
            "experiment_holdback_percent": holdback_percent_float,
            "experiment_variants": experiment_variants,
            "experiment_guardrail_thresholds": experiment_guardrail_thresholds,
        },
        errors,
    )


def validate_vton_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    model_alias = str(payload.get("model_alias", "baseline"))
    if model_alias not in SUPPORTED_VTON_ALIASES:
        errors.append({"field": "model_alias", "message": f"unsupported alias '{model_alias}'"})

    person_path = payload.get("person_image_path")
    garment_path = payload.get("garment_image_path")
    output_path = payload.get("output_image_path")
    if person_path is None:
        errors.append({"field": "person_image_path", "message": "local VTON inference requires person_image_path"})
    if garment_path is None:
        errors.append({"field": "garment_image_path", "message": "local VTON inference requires garment_image_path"})
    if output_path is None:
        errors.append({"field": "output_image_path", "message": "local VTON inference requires output_image_path"})

    for field, value in [("person_image_path", person_path), ("garment_image_path", garment_path)]:
        if value is not None:
            _validate_local_image_path(field, Path(str(value)), errors)

    routing_mode = str(payload.get("routing_mode", "direct"))
    if routing_mode not in {"direct", "canary"}:
        errors.append({"field": "routing_mode", "message": "routing_mode must be 'direct' or 'canary'"})

    canary_percent = payload.get("canary_percent", 0.0)
    try:
        canary_percent_float = float(canary_percent)
    except (TypeError, ValueError):
        canary_percent_float = -1.0
        errors.append({"field": "canary_percent", "message": "canary_percent must be numeric"})
    if canary_percent_float < 0.0 or canary_percent_float > 100.0:
        errors.append({"field": "canary_percent", "message": "canary_percent must be between 0 and 100"})

    user_id = str(payload.get("user_id", "anonymous")).strip() or "anonymous"
    if len(user_id) > 128:
        errors.append({"field": "user_id", "message": "user_id must be at most 128 characters"})

    quota_plan = str(payload.get("quota_plan", "free")).strip().lower() or "free"
    if quota_plan not in SUPPORTED_QUOTA_PLANS:
        errors.append({"field": "quota_plan", "message": f"quota_plan must be one of {sorted(SUPPORTED_QUOTA_PLANS)}"})

    timeout_ms_int = _validate_timeout_ms(payload, errors)

    return (
        {
            "model_alias": model_alias,
            "person_image_path": str(person_path) if person_path is not None else "",
            "garment_image_path": str(garment_path) if garment_path is not None else "",
            "output_image_path": str(output_path) if output_path is not None else "",
            "cache_dir": str(payload.get("cache_dir", "artifacts/cache/vton_preflight")),
            "routing_mode": routing_mode,
            "canary_percent": canary_percent_float,
            "user_id": user_id,
            "quota_plan": quota_plan,
            "timeout_ms": timeout_ms_int,
        },
        errors,
    )


def _validate_timeout_ms(payload: dict[str, Any], errors: list[dict[str, str]]) -> int:
    timeout_ms = payload.get("timeout_ms", DEFAULT_TIMEOUT_MS)
    try:
        timeout_ms_int = int(timeout_ms)
    except (TypeError, ValueError):
        timeout_ms_int = 0
        errors.append({"field": "timeout_ms", "message": "timeout_ms must be an integer"})
    if timeout_ms_int < 1 or timeout_ms_int > MAX_TIMEOUT_MS:
        errors.append({"field": "timeout_ms", "message": f"timeout_ms must be between 1 and {MAX_TIMEOUT_MS}"})
    return timeout_ms_int


def _validate_local_image_path(field: str, path: Path, errors: list[dict[str, str]]) -> None:
    if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        errors.append({"field": field, "message": "image must be PNG or JPEG"})
    if not path.exists():
        errors.append({"field": field, "message": "image path does not exist"})
        return
    if not path.is_file():
        errors.append({"field": field, "message": "image path must be a file"})
        return
    size_bytes = path.stat().st_size
    if size_bytes > MAX_IMAGE_BYTES:
        errors.append(
            {
                "field": field,
                "message": f"image exceeds {MAX_IMAGE_BYTES} byte limit",
            }
        )
