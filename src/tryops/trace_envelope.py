from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "tryops.native_trace_log_envelope.v1"

_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID = re.compile(r"^[0-9a-f]{16}$")
_TRACE_FLAGS = re.compile(r"^[0-9a-f]{2}$")
_SENSITIVE_KEYS = {
    "prompt",
    "raw_prompt",
    "person_image_path",
    "garment_image_path",
    "output_image_path",
    "api_key",
    "authorization",
    "token",
    "secret",
}


def build_native_trace_log_envelope(
    event: dict[str, Any],
    *,
    structured_log: dict[str, Any] | None = None,
    language: str = "fastapi",
    runtime: str = "python",
    component: str = "api",
    service_name: str = "tryops-api",
    service_version: str = "0.1.0",
) -> dict[str, Any]:
    attributes = dict((structured_log or {}).get("attributes", {}))
    if not attributes:
        attributes = {
            "endpoint": event.get("endpoint"),
            "model_alias": event.get("model_alias"),
            "model_version": event.get("model_version"),
            "status": event.get("status"),
            "latency_ms": event.get("latency_ms"),
            "payload_metadata": event.get("payload_metadata", {}),
        }
    attributes = _drop_none(attributes)
    trace = event.get("trace", {}) if isinstance(event.get("trace"), dict) else {}
    trace_id = str(event.get("trace_id") or trace.get("trace_id") or "")
    span_id = str(event.get("span_id") or trace.get("span_id") or "")
    trace_flags = str(trace.get("trace_flags") or (structured_log or {}).get("trace_flags") or "01")
    traceparent = str(event.get("traceparent") or f"00-{trace_id}-{span_id}-{trace_flags}")

    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": str(event.get("timestamp") or datetime.now(UTC).isoformat()),
        "observed_timestamp": str((structured_log or {}).get("observed_timestamp") or datetime.now(UTC).isoformat()),
        "language": language,
        "runtime": runtime,
        "component": component,
        "event_name": str((structured_log or {}).get("event_name") or "tryops.api.request"),
        "severity_text": str((structured_log or {}).get("severity_text") or "INFO"),
        "severity_number": int((structured_log or {}).get("severity_number") or 9),
        "trace_id": trace_id,
        "span_id": span_id,
        "trace_flags": trace_flags,
        "traceparent": traceparent,
        "request_id": str(event.get("request_id") or attributes.get("request_id") or ""),
        "workload": str(event.get("workload") or attributes.get("workload") or ""),
        "resource": {
            "service.name": service_name,
            "service.version": service_version,
            "telemetry.sdk.language": language,
        },
        "attributes": attributes,
    }


def validate_native_trace_log_envelope(envelope: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "schema_version",
        "timestamp",
        "observed_timestamp",
        "language",
        "runtime",
        "component",
        "event_name",
        "severity_text",
        "severity_number",
        "trace_id",
        "span_id",
        "trace_flags",
        "traceparent",
        "request_id",
        "workload",
        "resource",
        "attributes",
    ]
    for key in required:
        if key not in envelope:
            errors.append(f"missing {key}")
    if envelope.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")

    trace_id = str(envelope.get("trace_id", ""))
    span_id = str(envelope.get("span_id", ""))
    trace_flags = str(envelope.get("trace_flags", ""))
    traceparent = str(envelope.get("traceparent", ""))
    if not _TRACE_ID.fullmatch(trace_id) or _is_all_zero(trace_id):
        errors.append("invalid trace_id")
    if not _SPAN_ID.fullmatch(span_id) or _is_all_zero(span_id):
        errors.append("invalid span_id")
    if not _TRACE_FLAGS.fullmatch(trace_flags):
        errors.append("invalid trace_flags")
    if traceparent != f"00-{trace_id}-{span_id}-{trace_flags}":
        errors.append("traceparent does not match trace fields")

    resource = envelope.get("resource")
    if not isinstance(resource, dict):
        errors.append("resource must be an object")
    else:
        if not str(resource.get("service.name", "")).strip():
            errors.append("resource.service.name is required")
        if not str(resource.get("service.version", "")).strip():
            errors.append("resource.service.version is required")

    if not isinstance(envelope.get("attributes"), dict):
        errors.append("attributes must be an object")
    elif _has_sensitive_attribute(envelope["attributes"]):
        errors.append("attributes contain sensitive raw fields")
    if not str(envelope.get("event_name", "")).strip():
        errors.append("event_name is required")
    if int(envelope.get("severity_number") or 0) <= 0:
        errors.append("severity_number must be positive")
    return errors


def envelope_from_structured_log(record: dict[str, Any]) -> dict[str, Any]:
    envelope = record.get("native_envelope")
    if isinstance(envelope, dict):
        return envelope
    event = {
        "timestamp": record.get("timestamp"),
        "request_id": record.get("attributes", {}).get("request_id"),
        "workload": record.get("attributes", {}).get("workload"),
        "trace_id": record.get("trace_id"),
        "span_id": record.get("span_id"),
        "trace": {"trace_flags": record.get("trace_flags")},
        "traceparent": record.get("attributes", {}).get("traceparent"),
    }
    return build_native_trace_log_envelope(event, structured_log=record)


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _is_all_zero(value: str) -> bool:
    return all(ch == "0" for ch in value)


def _has_sensitive_attribute(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                return True
            if _has_sensitive_attribute(item):
                return True
        return False
    if isinstance(value, list):
        return any(_has_sensitive_attribute(item) for item in value)
    if isinstance(value, str):
        serialized = value.lower()
        if "bearer " in serialized or "api_key" in serialized or "secret prompt" in serialized:
            return True
    return False


def envelope_json(envelope: dict[str, Any]) -> str:
    return json.dumps(envelope, sort_keys=True)
