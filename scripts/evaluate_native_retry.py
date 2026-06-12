#!/usr/bin/env python3
"""Simulate the retry policy over a request stream with the native engine and
write an auditable report, cross-checking against the Python reference.
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

from tryops.native_retry import (  # noqa: E402
    RetryConfig,
    evaluate_with_native_retry,
    run_retry_reference,
)


def parse_wire(text: str):
    cfg = RetryConfig()
    needs = []
    for line in text.splitlines():
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key == "max_retries":
            cfg.max_retries = int(value)
        elif key == "base_backoff_ms":
            cfg.base_backoff_ms = float(value)
        elif key == "max_backoff_ms":
            cfg.max_backoff_ms = float(value)
        elif key == "jitter":
            cfg.jitter = value
        elif key == "retry_budget_ratio":
            cfg.retry_budget_ratio = float(value)
        elif key == "seed":
            cfg.seed = int(value)
        elif key == "request":
            f = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
            needs.append(int(f.get("attempts_needed", 1)))
    return cfg, needs


def main() -> int:
    parser = argparse.ArgumentParser(description="Native retry policy verdict.")
    parser.add_argument("--wire", type=Path, default=Path("samples/retry/requests.wire"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/retry/retry_report.json"))
    parser.add_argument("--min-success-rate", type=float, default=0.85)
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    cfg, needs = parse_wire(args.wire.read_text(encoding="utf-8"))
    report = evaluate_with_native_retry(
        needs, cfg, min_success_rate=args.min_success_rate, cli_path=args.cli
    )
    reference = run_retry_reference(needs, cfg)
    count_keys = (
        "requests", "successes", "failures", "retries_attempted",
        "retries_denied_budget", "retries_exhausted",
    )
    agrees = all(report.get(k) == reference.get(k) for k in count_keys) and (
        abs(report.get("total_backoff_ms", 0.0) - reference["total_backoff_ms"]) <= 1e-3
    )

    out = {
        "schema_version": "tryops.native_retry.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "wire": str(args.wire),
        "config": {
            "max_retries": cfg.max_retries, "base_backoff_ms": cfg.base_backoff_ms,
            "jitter": cfg.jitter, "retry_budget_ratio": cfg.retry_budget_ratio, "seed": cfg.seed,
        },
        "engine": report.get("engine"),
        "report": report,
        "reference_agrees": agrees,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(
        f"[retry] engine={report.get('engine')} requests={report['requests']} "
        f"success_rate={report['success_rate']:.3f} "
        f"(no_retry={report['success_rate_without_retry']:.3f}) "
        f"retries={report['retries_attempted']} denied={report['retries_denied_budget']} "
        f"backoff_ms={report['total_backoff_ms']:.0f} reference_agrees={agrees}"
    )
    print(f"[retry] wrote {args.output}")
    return 0 if (agrees and report.get("gate_ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
