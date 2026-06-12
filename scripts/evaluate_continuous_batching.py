#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_batch_scheduler import evaluate_with_native_batch_scheduler  # noqa: E402


RESEARCH_SOURCES = [
    {
        "name": "Orca OSDI 2022",
        "url": "https://www.usenix.org/conference/osdi22/presentation/yu",
        "use": "Iteration-level scheduling reference for transformer generation serving.",
    },
    {
        "name": "vLLM documentation",
        "url": "https://docs.vllm.ai/",
        "use": "Open-source serving target with continuous batching, chunked prefill, and PagedAttention.",
    },
    {
        "name": "vLLM performance tuning",
        "url": "https://docs.vllm.ai/en/v0.4.2/models/performance.html",
        "use": "Scheduler tuning reference for decode-prefill tradeoffs and max batched tokens.",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate native continuous batching scheduling evidence.")
    parser.add_argument(
        "--sensitivity",
        type=Path,
        default=Path("artifacts/eval/llm_sensitivity/sensitivity.json"),
        help="LLM sensitivity artifact used to seed mixed prompt/decode lengths.",
    )
    parser.add_argument(
        "--native-cli",
        type=Path,
        default=Path("artifacts/native/tryops_batch_scheduler_cli"),
        help="Compiled native C++ batch scheduler CLI.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/eval/llm_batching/continuous_batching_report.json"),
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--arrival-stride-ms", type=float, default=2.0)
    parser.add_argument("--prefill-token-ms", type=float, default=0.01)
    parser.add_argument("--decode-step-ms", type=float, default=0.18)
    parser.add_argument("--batch-growth-factor", type=float, default=0.08)
    parser.add_argument("--static-batch-wait-ms", type=float, default=0.0)
    args = parser.parse_args()

    sensitivity = _read_json(args.sensitivity)
    requests = build_mixed_request_stream(
        sensitivity,
        concurrency=args.concurrency,
        arrival_stride_ms=args.arrival_stride_ms,
    )
    native = evaluate_with_native_batch_scheduler(
        requests,
        max_num_seqs=args.concurrency,
        prefill_token_ms=args.prefill_token_ms,
        decode_step_ms=args.decode_step_ms,
        batch_growth_factor=args.batch_growth_factor,
        static_batch_wait_ms=args.static_batch_wait_ms,
        cli_path=args.native_cli,
    )
    checks = _build_checks(native, len(requests))
    report = {
        "schema_version": "tryops.llm_continuous_batching.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_artifacts": {
            "sensitivity": str(args.sensitivity),
            "native_cli": str(args.native_cli),
        },
        "research_sources": RESEARCH_SOURCES,
        "workload": {
            "request_count": len(requests),
            "concurrency": args.concurrency,
            "arrival_stride_ms": args.arrival_stride_ms,
            "min_prefill_tokens": min(int(item["prefill_tokens"]) for item in requests),
            "max_prefill_tokens": max(int(item["prefill_tokens"]) for item in requests),
            "min_decode_tokens": min(int(item["decode_tokens"]) for item in requests),
            "max_decode_tokens": max(int(item["decode_tokens"]) for item in requests),
            "requests": requests,
        },
        "scheduler_model": {
            "prefill_token_ms": args.prefill_token_ms,
            "decode_step_ms": args.decode_step_ms,
            "batch_growth_factor": args.batch_growth_factor,
            "static_batch_wait_ms": args.static_batch_wait_ms,
            "model_scope": "deterministic scheduler model seeded from local LLM sensitivity evidence",
        },
        "native_scheduler": native,
        "checks": checks,
        "passed": all(checks.values()),
        "notes": [
            "This is native scheduler evidence for E012, not a claim that vLLM serving is deployed.",
            "E011 remains separate: run a live vLLM server on the selected model when compatible hardware and dependencies are available.",
            "The comparison intentionally uses mixed prompt and output lengths because continuous batching mainly removes request-level padding and head-of-line blocking.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": checks, "output": str(args.output)}, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


def build_mixed_request_stream(
    sensitivity: dict[str, Any],
    *,
    concurrency: int = 4,
    arrival_stride_ms: float = 2.0,
) -> list[dict[str, Any]]:
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    prompt_records = sensitivity.get("prompt_length_sensitivity") or []
    output_records = sensitivity.get("output_length_sensitivity") or []
    if not prompt_records or not output_records:
        raise ValueError("sensitivity artifact must contain prompt and output length records")

    prompt_tokens = [
        int(record.get("actual_input_tokens", record.get("input_tokens", 0)))
        for record in sorted(prompt_records, key=lambda item: int(item.get("actual_input_tokens", item.get("input_tokens", 0))))
    ]
    decode_tokens = [
        int(record.get("output_tokens", record.get("max_tokens", 0)))
        for record in sorted(output_records, key=lambda item: int(item.get("max_tokens", item.get("output_tokens", 0))))
    ]
    if any(value < 1 for value in prompt_tokens + decode_tokens):
        raise ValueError("sensitivity token counts must be positive")

    request_count = len(prompt_tokens) * len(decode_tokens)
    requests: list[dict[str, Any]] = []
    for index in range(request_count):
        prefill_index = index % len(prompt_tokens)
        decode_index = (index * 2 + index // max(1, len(prompt_tokens))) % len(decode_tokens)
        burst = index // concurrency
        in_burst = index % concurrency
        requests.append(
            {
                "id": f"req-{index:03d}",
                "arrival_ms": round(burst * arrival_stride_ms + in_burst * 0.05, 6),
                "prefill_tokens": prompt_tokens[prefill_index],
                "decode_tokens": decode_tokens[decode_index],
                "source_prompt_case": prefill_index,
                "source_decode_case": decode_index,
            }
        )
    return requests


def _build_checks(native: dict[str, Any], request_count: int) -> dict[str, bool]:
    static = native.get("static_batching", {})
    continuous = native.get("continuous_batching", {})
    comparison = native.get("comparison", {})
    return {
        "native_scheduler_available": bool(native.get("available")),
        "static_completed_all": int(static.get("completed_requests", -1)) == request_count,
        "continuous_completed_all": int(continuous.get("completed_requests", -1)) == request_count,
        "throughput_gain_present": float(comparison.get("throughput_gain", 0.0)) > 0.0,
        "continuous_throughput_not_worse": float(continuous.get("tokens_per_second", 0.0))
        >= float(static.get("tokens_per_second", 1e18)),
        "continuous_p95_not_worse": float(continuous.get("latency_p95_ms", 1e18))
        <= float(static.get("latency_p95_ms", -1.0)),
        "continuous_decode_utilization_not_worse": float(continuous.get("decode_slot_utilization", 0.0))
        >= float(static.get("decode_slot_utilization", 1e18)),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
