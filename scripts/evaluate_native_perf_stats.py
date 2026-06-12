#!/usr/bin/env python3
"""Compute benchmark percentiles + SLO verdict using the native C++ engine.

Reads a ``tryops.llm_benchmark.v1`` artifact, extracts the per-request latency
and throughput samples, and delegates the statistics/SLO gating to the compiled
``tryops_perf_stats`` CLI. Writes a ``tryops.native_perf_stats.report.v1``
artifact so the production-language verdict is auditable alongside the run.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_perf_stats import evaluate_with_native_perf_stats  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Native C++ benchmark stats + SLO verdict.")
    parser.add_argument("--benchmark", type=Path, default=Path("artifacts/eval/llm_baseline/benchmark.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/perf_stats/perf_stats.json"))
    parser.add_argument("--latency-p95-ms-max", type=float, default=100.0)
    parser.add_argument("--tokens-per-second-min", type=float, default=5.0)
    args = parser.parse_args()

    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    records = benchmark.get("records", [])
    if not records:
        raise SystemExit(f"no records in {args.benchmark}")

    latency = [float(r["latency_ms"]) for r in records]
    throughput = [float(r["tokens_per_second"]) for r in records]

    stats = evaluate_with_native_perf_stats(
        latency,
        throughput,
        latency_p95_ms_max=args.latency_p95_ms_max,
        tokens_per_second_min=args.tokens_per_second_min,
    )

    report = {
        "schema_version": "tryops.native_perf_stats.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "benchmark_source": str(args.benchmark),
        "benchmark_adapter": benchmark.get("adapter", "unknown"),
        "sample_count": len(records),
        "slo_inputs": {
            "latency_p95_ms_max": args.latency_p95_ms_max,
            "tokens_per_second_min": args.tokens_per_second_min,
        },
        "native_stats": stats,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["native_stats"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
