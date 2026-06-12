from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from secrets import token_hex
from typing import Any


TRACE_CONTEXT_SCHEMA = "tryops.trace_context.v1"
TRACE_SPAN_SCHEMA = "tryops.trace_span.v1"
DEFAULT_TRACE_FLAGS = "01"
_TRACEPARENT_RE = re.compile(
    r"^(?P<version>[0-9a-f]{2})-"
    r"(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<span_id>[0-9a-f]{16})-"
    r"(?P<trace_flags>[0-9a-f]{2})(?:-.*)?$"
)


def parse_traceparent(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    match = _TRACEPARENT_RE.match(str(value).strip().lower())
    if match is None:
        return None
    parts = match.groupdict()
    if parts["version"] == "ff":
        return None
    if not _nonzero_hex(parts["trace_id"]) or not _nonzero_hex(parts["span_id"]):
        return None
    return parts


def extract_traceparent(carrier: dict[str, Any] | None) -> str | None:
    if not isinstance(carrier, dict):
        return None
    for key in ("traceparent", "trace_parent", "Traceparent"):
        value = carrier.get(key)
        if isinstance(value, str) and parse_traceparent(value):
            return value
    headers = carrier.get("headers")
    if isinstance(headers, dict):
        for key, value in headers.items():
            if str(key).lower() == "traceparent" and isinstance(value, str) and parse_traceparent(value):
                return value
    trace = carrier.get("trace")
    if isinstance(trace, dict):
        value = trace.get("traceparent")
        if isinstance(value, str) and parse_traceparent(value):
            return value
    return None


def build_trace_context(carrier: dict[str, Any] | None = None) -> dict[str, Any]:
    parent = parse_traceparent(extract_traceparent(carrier))
    if parent:
        trace_id = parent["trace_id"]
        parent_span_id = parent["span_id"]
        trace_flags = parent["trace_flags"]
        remote_parent = True
    else:
        trace_id = new_trace_id()
        parent_span_id = None
        trace_flags = DEFAULT_TRACE_FLAGS
        remote_parent = False
    span_id = new_span_id()
    return {
        "schema_version": TRACE_CONTEXT_SCHEMA,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "trace_flags": trace_flags,
        "traceparent": format_traceparent(trace_id=trace_id, span_id=span_id, trace_flags=trace_flags),
        "remote_parent": remote_parent,
        "sampled": trace_flags.endswith("1"),
    }


def build_api_server_span(
    *,
    endpoint: str,
    request_id: str,
    workload: str,
    model_alias: str,
    model_version: str,
    app_status: str,
    latency_ms: float,
    payload_metadata: dict[str, Any],
    carrier: dict[str, Any] | None = None,
    method: str = "POST",
    ended_at: datetime | None = None,
    phase_timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ended = ended_at or datetime.now(UTC)
    started = ended - timedelta(milliseconds=max(latency_ms, 0.0))
    context = build_trace_context(carrier)
    status_code = _http_status_code(app_status)
    attributes: dict[str, Any] = {
        "http.request.method": method.upper(),
        "http.route": endpoint,
        "http.response.status_code": status_code,
        "service.name": "tryops-api",
        "service.version": "0.1.0",
        "tryops.request_id": request_id,
        "tryops.workload": workload,
        "tryops.model_alias": model_alias,
        "tryops.model_version": model_version,
        "tryops.status": app_status,
    }
    if "quota_plan" in payload_metadata:
        attributes["tryops.quota.plan"] = payload_metadata["quota_plan"]
    if "user_hash" in payload_metadata:
        attributes["tryops.user_hash"] = payload_metadata["user_hash"]
    if phase_timing:
        if "source" in phase_timing:
            attributes["tryops.llm.phase_timing_source"] = phase_timing["source"]
        for key in ("prefill_ms", "decode_ms"):
            if key in phase_timing:
                attributes[f"tryops.llm.{key}"] = phase_timing[key]
    return {
        "schema_version": TRACE_SPAN_SCHEMA,
        "trace_id": context["trace_id"],
        "span_id": context["span_id"],
        "parent_span_id": context["parent_span_id"],
        "trace_flags": context["trace_flags"],
        "traceparent": context["traceparent"],
        "remote_parent": context["remote_parent"],
        "name": f"{method.upper()} {endpoint}",
        "kind": "SERVER",
        "start_time": started.isoformat(),
        "end_time": ended.isoformat(),
        "duration_ms": round(latency_ms, 3),
        "status": {
            "code": "ERROR" if str(app_status) in {"rejected", "failed", "error"} else "UNSET",
            "message": str(app_status),
        },
        "resource": {
            "service.name": "tryops-api",
            "service.version": "0.1.0",
        },
        "attributes": attributes,
    }


def public_trace_context(span: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": TRACE_CONTEXT_SCHEMA,
        "trace_id": span["trace_id"],
        "span_id": span["span_id"],
        "parent_span_id": span.get("parent_span_id"),
        "trace_flags": span["trace_flags"],
        "traceparent": span["traceparent"],
        "sampled": str(span["trace_flags"]).endswith("1"),
    }


def format_traceparent(*, trace_id: str, span_id: str, trace_flags: str = DEFAULT_TRACE_FLAGS) -> str:
    return f"00-{trace_id.lower()}-{span_id.lower()}-{trace_flags.lower()}"


def new_trace_id() -> str:
    return _new_nonzero_hex(32)


def new_span_id() -> str:
    return _new_nonzero_hex(16)


def _new_nonzero_hex(length: int) -> str:
    while True:
        value = token_hex(length // 2)
        if _nonzero_hex(value):
            return value


def _nonzero_hex(value: str) -> bool:
    return bool(value) and any(ch != "0" for ch in value)


def _http_status_code(app_status: str) -> int:
    if app_status == "accepted":
        return 202
    if app_status in {"completed", "ok", "ready"}:
        return 200
    if app_status in {"rejected", "invalid"}:
        return 400
    if app_status in {"failed", "error"}:
        return 500
    return 200
