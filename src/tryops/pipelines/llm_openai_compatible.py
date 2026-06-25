from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from time import perf_counter
from typing import Any

from tryops.pipelines.llm_baseline import _safety_flags, estimate_tokens
from tryops.pipelines.llm_phase_timing import PHASE_TIMING_SCHEMA


DEFAULT_LLM_MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"


class RealLLMUnavailableError(RuntimeError):
    """Raised when the configured real LLM serving endpoint cannot satisfy a request."""


def generate_openai_compatible_response(
    *,
    prompt: str,
    model_alias: str = "champion",
    max_tokens: int = 256,
    structured: bool = True,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Generate through a real OpenAI-compatible endpoint such as vLLM.

    This adapter intentionally has no deterministic fallback. Missing
    configuration, HTTP errors, invalid responses, and empty generations are
    surfaced to the caller as ``RealLLMUnavailableError``.
    """

    clean_prompt = str(prompt).strip()
    if not clean_prompt:
        raise ValueError("prompt cannot be empty")
    if len(clean_prompt) > 8000:
        raise ValueError("prompt exceeds the 8000 character local contract limit")
    if max_tokens < 1 or max_tokens > 2048:
        raise ValueError("max_tokens must be between 1 and 2048")

    config = _load_config(timeout_seconds=timeout_seconds)
    started = perf_counter()
    response_json = _post_chat_completion(
        prompt=clean_prompt,
        model=config["model"],
        max_tokens=max_tokens,
        temperature=config["temperature"],
        base_url=config["base_url"],
        api_key=config["api_key"],
        timeout_seconds=config["timeout_seconds"],
    )
    elapsed_ms = max((perf_counter() - started) * 1000.0, 0.001)

    text = _extract_text(response_json)
    if not text.strip():
        raise RealLLMUnavailableError("real LLM endpoint returned an empty completion")

    usage = response_json.get("usage", {}) if isinstance(response_json.get("usage"), dict) else {}
    input_tokens = _usage_int(usage, "prompt_tokens", estimate_tokens(clean_prompt))
    output_tokens = _usage_int(usage, "completion_tokens", estimate_tokens(text))
    total_tokens = _usage_int(usage, "total_tokens", input_tokens + output_tokens)
    finish_reason = _extract_finish_reason(response_json)
    tokens_per_second = output_tokens / max(elapsed_ms / 1000.0, 0.001)

    payload: dict[str, Any] = {
        "schema_version": "tryops.llm_generation.v1",
        "status": "completed",
        "model": {
            "alias": model_alias,
            "name": config["model"],
            "version": "openai-compatible",
            "adapter": "openai-compatible-vllm",
            "provider": config["provider"],
            "base_url": _public_base_url(config["base_url"]),
        },
        "prompt": {
            "characters": len(clean_prompt),
            "estimated_tokens": input_tokens,
            "class": "real_llm_request",
        },
        "output": {
            "text": text,
            "estimated_tokens": output_tokens,
            "truncated": finish_reason == "length",
        },
        "metrics": {
            "latency_ms": round(elapsed_ms, 3),
            "tokens_per_second": round(tokens_per_second, 6),
            "memory_gb": 0.0,
            "phase_timing": {
                "schema_version": PHASE_TIMING_SCHEMA,
                "available": False,
                "source": "openai-compatible-vllm",
                "semantics": "remote endpoint did not return prefill/decode phase timing",
                "total_latency_ms": round(elapsed_ms, 6),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        },
        "cost_estimate": _estimate_cost(input_tokens=input_tokens, output_tokens=output_tokens),
        "safety": _safety_flags(clean_prompt, text),
    }
    if structured:
        payload["structured_answer"] = {
            "intent": "real_model_response",
            "model": config["model"],
            "text": text,
            "total_tokens": total_tokens,
        }
    return payload


def _load_config(*, timeout_seconds: float | None) -> dict[str, Any]:
    base_url = str(os.environ.get("TRYOPS_LLM_BASE_URL", "")).strip()
    if not base_url:
        raise RealLLMUnavailableError(
            "TRYOPS_LLM_BASE_URL is required; start vLLM or set an OpenAI-compatible endpoint"
        )
    model = str(os.environ.get("TRYOPS_LLM_MODEL", DEFAULT_LLM_MODEL)).strip() or DEFAULT_LLM_MODEL
    provider = str(os.environ.get("TRYOPS_LLM_PROVIDER", "openai_compatible")).strip() or "openai_compatible"
    configured_timeout = _float_env("TRYOPS_LLM_TIMEOUT_SECONDS", 120.0)
    if timeout_seconds is not None:
        configured_timeout = max(0.001, min(configured_timeout, float(timeout_seconds)))
    return {
        "base_url": base_url.rstrip("/"),
        "model": model,
        "provider": provider,
        "api_key": os.environ.get("TRYOPS_LLM_API_KEY", ""),
        "timeout_seconds": configured_timeout,
        "temperature": _float_env("TRYOPS_LLM_TEMPERATURE", 0.0),
    }


def _post_chat_completion(
    *,
    prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    url = f"{base_url}/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read(1000).decode("utf-8", errors="replace")
        raise RealLLMUnavailableError(
            f"real LLM endpoint returned HTTP {exc.code}: {body_text.strip() or exc.reason}"
        ) from exc
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        raise RealLLMUnavailableError(f"real LLM endpoint is unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RealLLMUnavailableError("real LLM endpoint returned invalid JSON") from exc


def _extract_text(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RealLLMUnavailableError("real LLM endpoint response did not include choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise RealLLMUnavailableError("real LLM endpoint choice was not an object")
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(first.get("text"), str):
        return first["text"]
    raise RealLLMUnavailableError("real LLM endpoint response did not include completion text")


def _extract_finish_reason(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return str(choices[0].get("finish_reason", ""))
    return ""


def _usage_int(usage: dict[str, Any], key: str, default: int) -> int:
    try:
        return max(0, int(usage.get(key, default)))
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _estimate_cost(*, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    input_rate = _float_env("TRYOPS_LLM_INPUT_COST_PER_1K_USD", 0.0)
    output_rate = _float_env("TRYOPS_LLM_OUTPUT_COST_PER_1K_USD", 0.0)
    request_usd = (input_tokens / 1000.0 * input_rate) + (output_tokens / 1000.0 * output_rate)
    return {
        "request_usd": round(request_usd, 9),
        "per_1k_input_tokens_usd": input_rate,
        "per_1k_output_tokens_usd": output_rate,
        "total_tokens": input_tokens + output_tokens,
        "basis": "configured real LLM serving endpoint cost rates",
    }


def _public_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if not parsed.netloc:
        return base_url
    safe_netloc = parsed.hostname or parsed.netloc
    if parsed.port:
        safe_netloc = f"{safe_netloc}:{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, safe_netloc, parsed.path, "", ""))
