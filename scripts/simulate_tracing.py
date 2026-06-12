#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.observability import (  # noqa: E402
    configure_structured_log_path,
    configure_trace_span_path,
    read_structured_log_file,
    read_trace_span_file,
    record_api_observation,
    render_prometheus_metrics,
    reset_metrics,
    start_timer,
    structured_logs_snapshot,
    trace_spans_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local OpenTelemetry-compatible trace evidence.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/traces/trace_sample.json"))
    parser.add_argument("--span-output", type=Path, default=Path("artifacts/eval/traces/api_spans.jsonl"))
    parser.add_argument("--log-output", type=Path, default=Path("artifacts/eval/traces/api_events.jsonl"))
    args = parser.parse_args()

    parent = "00-11111111111111111111111111111111-2222222222222222-01"
    reset_metrics()
    configure_trace_span_path(args.span_output, truncate=True)
    configure_structured_log_path(args.log_output, truncate=True)
    try:
        llm_event = record_api_observation(
            endpoint="/v1/llm/generate",
            request_id="req-trace-llm",
            workload="llm",
            model_alias="baseline",
            status="completed",
            started_at=start_timer(),
            payload={
                "prompt": "private prompt must not enter trace attributes",
                "model_alias": "baseline",
                "quota_plan": "free",
                "user_id": "customer-trace",
                "traceparent": parent,
            },
            response={
                "model": {"version": "0.1.0"},
                "metrics": {
                    "tokens_per_second": 100.0,
                    "memory_gb": 0.01,
                    "phase_timing": {
                        "available": True,
                        "source": "trace-sample",
                        "prefill_ms": 1.0,
                        "decode_ms": 3.0,
                    },
                },
                "status": "completed",
            },
        )
        vton_event = record_api_observation(
            endpoint="/v1/vton/infer",
            request_id="req-trace-vton",
            workload="vton",
            model_alias="champion",
            status="rejected",
            started_at=start_timer(),
            payload={
                "person_image_path": "/private/person.png",
                "garment_image_path": "/private/garment.png",
                "quota_plan": "free",
                "user_id": "customer-trace",
            },
            response={"status": "rejected", "error": {"code": "invalid_vton_request"}},
        )
        spans = trace_spans_snapshot()
        logs = structured_logs_snapshot()
        file_spans = read_trace_span_file(args.span_output)
        file_logs = read_structured_log_file(args.log_output)
        prometheus = render_prometheus_metrics()
    finally:
        configure_trace_span_path(None)
        configure_structured_log_path(None)

    serialized = json.dumps({"spans": spans, "logs": logs}, sort_keys=True)
    checks = {
        "span_count": len(spans) == 2,
        "jsonl_span_count": len(file_spans) == 2,
        "jsonl_log_count": len(file_logs) == 2,
        "parent_trace_propagated": llm_event["trace"]["trace_id"] == "11111111111111111111111111111111",
        "remote_parent_recorded": spans[0]["remote_parent"] is True,
        "raw_prompt_not_traced": "private prompt" not in serialized,
        "image_paths_not_traced": "/private/person.png" not in serialized,
        "prometheus_trace_metrics": "tryops_trace_spans_total" in prometheus,
        "rejected_span_marked_error": spans[1]["status"]["code"] == "ERROR",
    }
    report = {
        "schema_version": "tryops.trace_sample.v1",
        "passed": all(checks.values()),
        "checks": checks,
        "events": [llm_event, vton_event],
        "span_output": str(args.span_output),
        "log_output": str(args.log_output),
        "spans": spans,
        "prometheus_metric_names": [
            "tryops_trace_spans_total",
            "tryops_trace_span_duration_ms_sum",
            "tryops_trace_span_duration_ms_count",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
