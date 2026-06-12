from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from tryops.quota import user_hash
from tryops.trace_envelope import build_native_trace_log_envelope
from tryops.tracing import build_api_server_span, public_trace_context

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]


_EVENTS: list[dict[str, Any]] = []
_STRUCTURED_LOGS: list[dict[str, Any]] = []
_COUNTERS: dict[tuple[str, str, str, str], int] = defaultdict(int)
_LATENCY_SUMS: dict[tuple[str, str, str], float] = defaultdict(float)
_LATENCY_COUNTS: dict[tuple[str, str, str], int] = defaultdict(int)
_LLM_PHASE_SUMS: dict[tuple[str, str, str, str], float] = defaultdict(float)
_LLM_PHASE_COUNTS: dict[tuple[str, str, str, str], int] = defaultdict(int)
_TRACE_SPANS: list[dict[str, Any]] = []
_TRACE_SPAN_COUNTS: dict[tuple[str, str, str, str], int] = defaultdict(int)
_TRACE_SPAN_DURATION_SUMS: dict[tuple[str, str, str, str], float] = defaultdict(float)
_GUARDRAIL_COUNTS: dict[tuple[str, str, str], int] = defaultdict(int)
_SEMANTIC_CACHE_COUNTS: dict[tuple[str, str, str], int] = defaultdict(int)
_SEMANTIC_CACHE_SAVINGS: dict[tuple[str, str, str], float] = defaultdict(float)
_LOG_PATH: Path | None = Path(os.environ.get("TRYOPS_STRUCTURED_LOG_PATH", "artifacts/logs/api_events.jsonl"))
_TRACE_SPAN_PATH: Path | None = Path(os.environ.get("TRYOPS_TRACE_SPAN_PATH", "artifacts/traces/api_spans.jsonl"))


def start_timer() -> float:
    return perf_counter()


def record_api_observation(
    *,
    endpoint: str,
    request_id: str,
    workload: str,
    model_alias: str,
    status: str,
    started_at: float,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    latency_ms = round((perf_counter() - started_at) * 1000.0, 3)
    observed_at = datetime.now(UTC)
    model_version = _find_model_version(response)
    tokens_per_second = _find_metric(response, "tokens_per_second")
    memory_gb = _find_metric(response, "memory_gb")
    phase_timing = _find_phase_timing(response)
    if memory_gb is None:
        memory_gb = current_process_memory_gb()
    payload_metadata = sanitize_payload_metadata(workload=workload, payload=payload)
    app_status = str(status)
    span = build_api_server_span(
        endpoint=endpoint,
        request_id=request_id,
        workload=workload,
        model_alias=model_alias,
        model_version=model_version,
        app_status=app_status,
        latency_ms=latency_ms,
        payload_metadata=payload_metadata,
        carrier=payload,
        ended_at=observed_at,
        phase_timing=phase_timing,
    )
    trace_context = public_trace_context(span)

    event = {
        "timestamp": observed_at.isoformat(),
        "endpoint": endpoint,
        "request_id": request_id,
        "workload": workload,
        "model_alias": model_alias,
        "model_version": model_version,
        "status": app_status,
        "latency_ms": latency_ms,
        "tokens_per_second": tokens_per_second,
        "memory_gb": memory_gb,
        "llm_prefill_ms": phase_timing.get("prefill_ms") if phase_timing else None,
        "llm_decode_ms": phase_timing.get("decode_ms") if phase_timing else None,
        "llm_phase_timing_source": phase_timing.get("source") if phase_timing else None,
        "trace_id": trace_context["trace_id"],
        "span_id": trace_context["span_id"],
        "traceparent": trace_context["traceparent"],
        "trace": trace_context,
        "payload_metadata": payload_metadata,
    }
    _EVENTS.append(event)
    _COUNTERS[(endpoint, workload, model_alias, app_status)] += 1
    _LATENCY_SUMS[(endpoint, workload, model_alias)] += latency_ms
    _LATENCY_COUNTS[(endpoint, workload, model_alias)] += 1
    _TRACE_SPANS.append(span)
    _TRACE_SPAN_COUNTS[(endpoint, workload, model_alias, app_status)] += 1
    _TRACE_SPAN_DURATION_SUMS[(endpoint, workload, model_alias, app_status)] += latency_ms
    for guardrail in _guardrail_findings(response):
        _GUARDRAIL_COUNTS[(guardrail["owasp_id"], guardrail["action"], app_status)] += 1
    cache_meta = _semantic_cache_summary(response)
    if cache_meta:
        result = "hit" if cache_meta["hit"] else "miss"
        _SEMANTIC_CACHE_COUNTS[(workload, model_alias, result)] += 1
        _SEMANTIC_CACHE_SAVINGS[(workload, model_alias, "cost_usd")] += float(cache_meta["cost_saved_usd"])
        _SEMANTIC_CACHE_SAVINGS[(workload, model_alias, "energy_wh")] += float(cache_meta["energy_saved_wh"])
    if workload == "llm" and phase_timing:
        for phase in ("prefill", "decode"):
            key = f"{phase}_ms"
            if key in phase_timing:
                _LLM_PHASE_SUMS[(endpoint, workload, model_alias, phase)] += float(phase_timing[key])
                _LLM_PHASE_COUNTS[(endpoint, workload, model_alias, phase)] += 1
    emit_trace_span(span)
    emit_structured_log(event, response=response)
    return event


def sanitize_payload_metadata(*, workload: str, payload: dict[str, Any]) -> dict[str, Any]:
    if workload == "llm":
        prompt = payload.get("prompt", "")
        return {
            "prompt_chars": len(prompt) if isinstance(prompt, str) else 0,
            "max_tokens": payload.get("max_tokens", 256),
            "model_alias": payload.get("model_alias", "baseline"),
            "routing_mode": payload.get("routing_mode", "direct"),
            "shadow": bool(payload.get("shadow", False)),
            "fallback_enabled": bool(payload.get("fallback_enabled", False)),
            "semantic_cache_enabled": bool(payload.get("semantic_cache_enabled", True)),
            "user_hash": user_hash(str(payload.get("user_id", "anonymous"))),
            "quota_plan": payload.get("quota_plan", "free"),
        }
    if workload == "vton":
        image_fields = ["person_image_path", "garment_image_path"]
        return {
            "image_count": sum(1 for field in image_fields if field in payload),
            "has_output_path": "output_image_path" in payload,
            "model_alias": payload.get("model_alias", "champion"),
            "routing_mode": payload.get("routing_mode", "direct"),
            "user_hash": user_hash(str(payload.get("user_id", "anonymous"))),
            "quota_plan": payload.get("quota_plan", "free"),
        }
    return {"payload_keys": sorted(payload.keys())}


def metrics_snapshot() -> dict[str, Any]:
    return {
        "events": list(_EVENTS),
        "request_counters": [
            {
                "endpoint": endpoint,
                "workload": workload,
                "model_alias": model_alias,
                "status": status,
                "count": count,
            }
            for (endpoint, workload, model_alias, status), count in sorted(_COUNTERS.items())
        ],
        "latency": [
            {
                "endpoint": endpoint,
                "workload": workload,
                "model_alias": model_alias,
                "count": _LATENCY_COUNTS[(endpoint, workload, model_alias)],
                "sum_ms": round(total, 3),
                "avg_ms": round(total / _LATENCY_COUNTS[(endpoint, workload, model_alias)], 3),
            }
            for (endpoint, workload, model_alias), total in sorted(_LATENCY_SUMS.items())
        ],
        "trace_spans": list(_TRACE_SPANS),
        "trace_span_counters": [
            {
                "endpoint": endpoint,
                "workload": workload,
                "model_alias": model_alias,
                "status": status,
                "count": count,
                "duration_sum_ms": round(_TRACE_SPAN_DURATION_SUMS[(endpoint, workload, model_alias, status)], 3),
            }
            for (endpoint, workload, model_alias, status), count in sorted(_TRACE_SPAN_COUNTS.items())
        ],
        "guardrail_counters": [
            {
                "owasp_id": owasp_id,
                "action": action,
                "status": status,
                "count": count,
            }
            for (owasp_id, action, status), count in sorted(_GUARDRAIL_COUNTS.items())
        ],
        "semantic_cache_counters": [
            {
                "workload": workload,
                "model_alias": model_alias,
                "result": result,
                "count": count,
            }
            for (workload, model_alias, result), count in sorted(_SEMANTIC_CACHE_COUNTS.items())
        ],
    }


def emit_structured_log(event: dict[str, Any], *, response: dict[str, Any] | None = None) -> dict[str, Any]:
    record = {
        "schema_version": "tryops.structured_log.v1",
        "timestamp": event.get("timestamp", datetime.now(UTC).isoformat()),
        "observed_timestamp": datetime.now(UTC).isoformat(),
        "severity_text": _severity_text(event.get("status")),
        "severity_number": _severity_number(event.get("status")),
        "event_name": "tryops.api.request",
        "body": "API request observed",
        "resource": {
            "service.name": "tryops-api",
            "service.version": "0.1.0",
        },
        "attributes": {
            "endpoint": event.get("endpoint"),
            "request_id": event.get("request_id"),
            "workload": event.get("workload"),
            "model_alias": event.get("model_alias"),
            "model_version": event.get("model_version"),
            "status": event.get("status"),
            "latency_ms": event.get("latency_ms"),
            "tokens_per_second": event.get("tokens_per_second"),
            "memory_gb": event.get("memory_gb"),
            "llm_prefill_ms": event.get("llm_prefill_ms"),
            "llm_decode_ms": event.get("llm_decode_ms"),
            "llm_phase_timing_source": event.get("llm_phase_timing_source"),
            "trace_id": event.get("trace_id"),
            "span_id": event.get("span_id"),
            "traceparent": event.get("traceparent"),
            "payload_metadata": event.get("payload_metadata", {}),
            "guardrails": _guardrail_summary(response or {}),
            "semantic_cache": _semantic_cache_summary(response or {}),
            "error_code": _error_code(response or {}),
        },
        "trace_id": event.get("trace_id"),
        "span_id": event.get("span_id"),
        "trace_flags": event.get("trace", {}).get("trace_flags"),
    }
    record["native_envelope"] = build_native_trace_log_envelope(event, structured_log=record)
    _STRUCTURED_LOGS.append(record)
    if _LOG_PATH is not None:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def emit_trace_span(span: dict[str, Any]) -> dict[str, Any]:
    if _TRACE_SPAN_PATH is not None:
        _TRACE_SPAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _TRACE_SPAN_PATH.open("a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(span, sort_keys=True) + "\n")
    return span


def structured_logs_snapshot() -> list[dict[str, Any]]:
    return list(_STRUCTURED_LOGS)


def trace_spans_snapshot() -> list[dict[str, Any]]:
    return list(_TRACE_SPANS)


def configure_structured_log_path(path: str | Path | None, *, truncate: bool = False) -> None:
    global _LOG_PATH
    _LOG_PATH = Path(path) if path is not None else None
    if truncate and _LOG_PATH is not None:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LOG_PATH.write_text("", encoding="utf-8")


def configure_trace_span_path(path: str | Path | None, *, truncate: bool = False) -> None:
    global _TRACE_SPAN_PATH
    _TRACE_SPAN_PATH = Path(path) if path is not None else None
    if truncate and _TRACE_SPAN_PATH is not None:
        _TRACE_SPAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TRACE_SPAN_PATH.write_text("", encoding="utf-8")


def read_structured_log_file(path: str | Path) -> list[dict[str, Any]]:
    records = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def read_trace_span_file(path: str | Path) -> list[dict[str, Any]]:
    records = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def render_prometheus_metrics() -> str:
    lines = [
        "# HELP tryops_api_requests_total Total API requests by endpoint, workload, alias, and status.",
        "# TYPE tryops_api_requests_total counter",
    ]
    for (endpoint, workload, model_alias, status), count in sorted(_COUNTERS.items()):
        lines.append(
            "tryops_api_requests_total"
            f'{{endpoint="{_label(endpoint)}",workload="{_label(workload)}",'
            f'model_alias="{_label(model_alias)}",status="{_label(status)}"}} {count}'
        )
    lines.extend(
        [
            "# HELP tryops_api_latency_ms_sum Sum of API request latency in milliseconds.",
            "# TYPE tryops_api_latency_ms_sum counter",
        ]
    )
    for (endpoint, workload, model_alias), total in sorted(_LATENCY_SUMS.items()):
        labels = (
            f'endpoint="{_label(endpoint)}",workload="{_label(workload)}",'
            f'model_alias="{_label(model_alias)}"'
        )
        lines.append(f"tryops_api_latency_ms_sum{{{labels}}} {round(total, 3)}")
        lines.append(f"tryops_api_latency_ms_count{{{labels}}} {_LATENCY_COUNTS[(endpoint, workload, model_alias)]}")
    lines.extend(
        [
            "# HELP tryops_trace_spans_total Total local OpenTelemetry-compatible spans by endpoint, workload, alias, and status.",
            "# TYPE tryops_trace_spans_total counter",
        ]
    )
    for (endpoint, workload, model_alias, status), count in sorted(_TRACE_SPAN_COUNTS.items()):
        labels = (
            f'endpoint="{_label(endpoint)}",workload="{_label(workload)}",'
            f'model_alias="{_label(model_alias)}",status="{_label(status)}"'
        )
        lines.append(f"tryops_trace_spans_total{{{labels}}} {count}")
        lines.append(
            f"tryops_trace_span_duration_ms_sum{{{labels}}} "
            f"{round(_TRACE_SPAN_DURATION_SUMS[(endpoint, workload, model_alias, status)], 3)}"
        )
        lines.append(f"tryops_trace_span_duration_ms_count{{{labels}}} {count}")
    lines.extend(
        [
            "# HELP tryops_llm_phase_latency_ms_sum Sum of LLM prefill/decode phase timing in milliseconds.",
            "# TYPE tryops_llm_phase_latency_ms_sum counter",
        ]
    )
    for (endpoint, workload, model_alias, phase), total in sorted(_LLM_PHASE_SUMS.items()):
        labels = (
            f'endpoint="{_label(endpoint)}",workload="{_label(workload)}",'
            f'model_alias="{_label(model_alias)}",phase="{_label(phase)}"'
        )
        lines.append(f"tryops_llm_phase_latency_ms_sum{{{labels}}} {round(total, 3)}")
        lines.append(
            f"tryops_llm_phase_latency_ms_count{{{labels}}} {_LLM_PHASE_COUNTS[(endpoint, workload, model_alias, phase)]}"
        )
    lines.extend(
        [
            "# HELP tryops_guardrail_events_total Total guardrail findings by OWASP risk, action, and request status.",
            "# TYPE tryops_guardrail_events_total counter",
        ]
    )
    for (owasp_id, action, status), count in sorted(_GUARDRAIL_COUNTS.items()):
        labels = f'owasp_id="{_label(owasp_id)}",action="{_label(action)}",status="{_label(status)}"'
        lines.append(f"tryops_guardrail_events_total{{{labels}}} {count}")
    lines.extend(
        [
            "# HELP tryops_semantic_cache_requests_total Total semantic-cache lookups by workload, alias, and result.",
            "# TYPE tryops_semantic_cache_requests_total counter",
        ]
    )
    for (workload, model_alias, result), count in sorted(_SEMANTIC_CACHE_COUNTS.items()):
        labels = f'workload="{_label(workload)}",model_alias="{_label(model_alias)}",result="{_label(result)}"'
        lines.append(f"tryops_semantic_cache_requests_total{{{labels}}} {count}")
    lines.extend(
        [
            "# HELP tryops_semantic_cache_savings_total Estimated savings from semantic-cache hits.",
            "# TYPE tryops_semantic_cache_savings_total counter",
        ]
    )
    for (workload, model_alias, unit), total in sorted(_SEMANTIC_CACHE_SAVINGS.items()):
        labels = f'workload="{_label(workload)}",model_alias="{_label(model_alias)}",unit="{_label(unit)}"'
        lines.append(f"tryops_semantic_cache_savings_total{{{labels}}} {round(total, 9)}")
    lines.append(f"tryops_process_memory_gb {current_process_memory_gb()}")
    return "\n".join(lines) + "\n"


def reset_metrics() -> None:
    _EVENTS.clear()
    _STRUCTURED_LOGS.clear()
    _COUNTERS.clear()
    _LATENCY_SUMS.clear()
    _LATENCY_COUNTS.clear()
    _LLM_PHASE_SUMS.clear()
    _LLM_PHASE_COUNTS.clear()
    _TRACE_SPANS.clear()
    _TRACE_SPAN_COUNTS.clear()
    _TRACE_SPAN_DURATION_SUMS.clear()
    _GUARDRAIL_COUNTS.clear()
    _SEMANTIC_CACHE_COUNTS.clear()
    _SEMANTIC_CACHE_SAVINGS.clear()


def current_process_memory_gb() -> float:
    if resource is None:
        return 0.0
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if usage <= 0:
        return 0.0
    return round(usage / (1024.0 * 1024.0), 6)


def _find_model_version(response: dict[str, Any]) -> str:
    model = response.get("model")
    if isinstance(model, dict) and "version" in model:
        return str(model["version"])
    report = response.get("report")
    if isinstance(report, dict):
        report_model = report.get("model")
        if isinstance(report_model, dict) and "version" in report_model:
            return str(report_model["version"])
    return "unknown"


def _find_metric(response: dict[str, Any], key: str) -> float | None:
    metrics = response.get("metrics")
    if isinstance(metrics, dict) and key in metrics:
        return float(metrics[key])
    report = response.get("report")
    if isinstance(report, dict):
        report_metrics = report.get("metrics")
        if isinstance(report_metrics, dict) and key in report_metrics:
            return float(report_metrics[key])
    return None


def _find_phase_timing(response: dict[str, Any]) -> dict[str, Any]:
    metrics = response.get("metrics")
    if isinstance(metrics, dict):
        phase_timing = metrics.get("phase_timing")
        if isinstance(phase_timing, dict) and phase_timing.get("available"):
            return phase_timing
    report = response.get("report")
    if isinstance(report, dict):
        report_metrics = report.get("metrics")
        if isinstance(report_metrics, dict):
            phase_timing = report_metrics.get("phase_timing")
            if isinstance(phase_timing, dict) and phase_timing.get("available"):
                return phase_timing
    return {}


def _error_code(response: dict[str, Any]) -> str | None:
    error = response.get("error")
    if isinstance(error, dict) and "code" in error:
        return str(error["code"])
    return None


def _guardrail_findings(response: dict[str, Any]) -> list[dict[str, str]]:
    guardrails = response.get("guardrails")
    if not isinstance(guardrails, dict):
        return []
    findings = []
    for item in guardrails.get("findings", []):
        if not isinstance(item, dict):
            continue
        findings.append(
            {
                "owasp_id": str(item.get("owasp_id", "unknown")),
                "action": str(item.get("action", "review")),
            }
        )
    return findings


def _guardrail_summary(response: dict[str, Any]) -> dict[str, Any]:
    guardrails = response.get("guardrails")
    if not isinstance(guardrails, dict):
        return {}
    return {
        "schema_version": guardrails.get("schema_version"),
        "status": guardrails.get("status"),
        "blocked": bool(guardrails.get("blocked", False)),
        "risk_ids": guardrails.get("risk_ids", []),
        "action_counts": guardrails.get("action_counts", {}),
    }


def _semantic_cache_summary(response: dict[str, Any]) -> dict[str, Any]:
    cache = response.get("semantic_cache")
    if not isinstance(cache, dict):
        return {}
    lookup = cache.get("lookup", {}) if isinstance(cache.get("lookup"), dict) else {}
    savings = cache.get("savings", {}) if isinstance(cache.get("savings"), dict) else {}
    return {
        "schema_version": cache.get("schema_version"),
        "hit": bool(lookup.get("hit", False)),
        "matched_entry_id": str(lookup.get("matched_entry_id", "")),
        "score": float(lookup.get("score", 0.0) or 0.0),
        "tokens_saved": int(savings.get("tokens_saved", 0) or 0),
        "cost_saved_usd": float(savings.get("cost_saved_usd", 0.0) or 0.0),
        "energy_saved_wh": float(savings.get("energy_saved_wh", 0.0) or 0.0),
    }


def _severity_text(status: Any) -> str:
    return "ERROR" if str(status) in {"rejected", "failed", "error"} else "INFO"


def _severity_number(status: Any) -> int:
    return 17 if _severity_text(status) == "ERROR" else 9


def _label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
