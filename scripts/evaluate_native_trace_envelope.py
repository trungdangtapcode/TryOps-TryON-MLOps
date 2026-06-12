from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from time import sleep

from tryops.observability import (
    configure_structured_log_path,
    configure_trace_span_path,
    read_structured_log_file,
    record_api_observation,
    reset_metrics,
    start_timer,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build native trace/log envelope evidence across Rust, Go, C++, and FastAPI.")
    parser.add_argument("--work-dir", type=Path, default=Path("artifacts/eval/trace_envelope"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/trace_envelope/native_trace_envelope_report.json"))
    parser.add_argument("--go-cli", type=Path, default=Path("artifacts/native/tryops_trace_envelope"))
    parser.add_argument("--cpp-cli", type=Path, default=Path("artifacts/native/tryops_trace_envelope_cli"))
    args = parser.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    fastapi_envelope = generate_fastapi_envelope(args.work_dir)
    cpp_report = run_cpp_validator(args.cpp_cli)
    envelopes = [
        rust_gateway_envelope(),
        go_validator_envelope(),
        cpp_report["envelope"],
        fastapi_envelope,
    ]
    input_path = args.work_dir / "native_trace_envelopes.json"
    input_path.write_text(json.dumps({"envelopes": envelopes}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = run_go_report(args.go_cli, input_path, args.output)
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("passed") else 1


def generate_fastapi_envelope(work_dir: Path) -> dict[str, object]:
    log_path = work_dir / "fastapi_api_events.jsonl"
    span_path = work_dir / "fastapi_api_spans.jsonl"
    reset_metrics()
    configure_structured_log_path(log_path, truncate=True)
    configure_trace_span_path(span_path, truncate=True)
    try:
        started = start_timer()
        sleep(0.001)
        record_api_observation(
            endpoint="/v1/llm/generate",
            request_id="req-fastapi-envelope",
            workload="llm",
            model_alias="baseline",
            status="completed",
            started_at=started,
            payload={
                "prompt": "summarize enterprise trace envelope",
                "model_alias": "baseline",
                "user_id": "enterprise-user",
                "quota_plan": "enterprise",
            },
            response={
                "status": "completed",
                "model": {"version": "0.1.0"},
                "metrics": {"tokens_per_second": 128.0, "memory_gb": 0.01},
            },
        )
        records = read_structured_log_file(log_path)
    finally:
        configure_structured_log_path(None)
        configure_trace_span_path(None)
    if not records:
        raise RuntimeError("FastAPI structured log did not produce an envelope")
    return records[-1]["native_envelope"]


def run_cpp_validator(cpp_cli: Path) -> dict[str, object]:
    completed = subprocess.run(
        [str(cpp_cli)],
        input="",
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"C++ trace envelope validator failed: {completed.stderr or completed.stdout}")
    report = json.loads(completed.stdout)
    if not report.get("passed"):
        raise RuntimeError(f"C++ trace envelope did not pass: {report}")
    return report


def run_go_report(go_cli: Path, input_path: Path, output_path: Path) -> dict[str, object]:
    completed = subprocess.run(
        [str(go_cli), "--input", str(input_path), "--output", str(output_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Go trace envelope report failed: {completed.stderr or completed.stdout}")
    if output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    return json.loads(completed.stdout)


def rust_gateway_envelope() -> dict[str, object]:
    return {
        "schema_version": "tryops.native_trace_log_envelope.v1",
        "timestamp": "2026-06-12T00:00:00Z",
        "observed_timestamp": "2026-06-12T00:00:00Z",
        "language": "rust",
        "runtime": "tokio-axum",
        "component": "edge-gateway",
        "event_name": "tryops.gateway.proxy.request",
        "severity_text": "INFO",
        "severity_number": 9,
        "trace_id": "66666666666666666666666666666666",
        "span_id": "7777777777777777",
        "trace_flags": "01",
        "traceparent": "00-66666666666666666666666666666666-7777777777777777-01",
        "request_id": "req-rust-envelope",
        "workload": "llm",
        "resource": {
            "service.name": "tryops-gateway",
            "service.version": "0.1.0",
            "telemetry.sdk.language": "rust",
        },
        "attributes": {
            "endpoint": "/v1/llm/generate",
            "method": "POST",
            "status": "forwarded",
        },
    }


def go_validator_envelope() -> dict[str, object]:
    return {
        "schema_version": "tryops.native_trace_log_envelope.v1",
        "timestamp": "2026-06-12T00:00:00Z",
        "observed_timestamp": "2026-06-12T00:00:00Z",
        "language": "go",
        "runtime": "go1.22",
        "component": "native-validator",
        "event_name": "tryops.go.trace_envelope.validation",
        "severity_text": "INFO",
        "severity_number": 9,
        "trace_id": "44444444444444444444444444444444",
        "span_id": "5555555555555555",
        "trace_flags": "01",
        "traceparent": "00-44444444444444444444444444444444-5555555555555555-01",
        "request_id": "req-go-envelope",
        "workload": "platform",
        "resource": {
            "service.name": "tryops-native-go",
            "service.version": "0.1.0",
            "telemetry.sdk.language": "go",
        },
        "attributes": {
            "endpoint": "native://trace-envelope",
            "status": "validated",
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
