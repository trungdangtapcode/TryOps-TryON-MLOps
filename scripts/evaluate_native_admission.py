#!/usr/bin/env python3
"""Run the native admission controller over a request-event wire stream and
write an auditable report artifact.

The admission decision (rate limit / circuit breaker / bulkhead) is made by the
compiled C++ engine on the production boundary; this script only marshals the
event stream and records the verdict. It also cross-checks the native counts
against the Python reference reimplementation so any divergence is caught.
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

from tryops.native_admission import (  # noqa: E402
    evaluate_with_native_admission,
    parse_wire_events,
)

_COUNT_KEYS = (
    "total",
    "admitted",
    "rejected_rate_limited",
    "rejected_breaker_open",
    "rejected_concurrency_full",
    "breaker_trips",
    "breaker_recoveries",
    "peak_inflight",
    "final_breaker_state",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Native admission controller verdict.")
    parser.add_argument(
        "--wire",
        type=Path,
        default=Path("samples/admission/mixed_traffic.wire"),
        help="request-event wire stream",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/admission/admission_report.json"),
    )
    parser.add_argument("--max-shed-rate", type=float, default=0.7)
    parser.add_argument(
        "--cli",
        type=Path,
        default=None,
        help="path to tryops_admission_cli (defaults to artifacts/native/...)",
    )
    args = parser.parse_args()

    text = args.wire.read_text(encoding="utf-8")
    config, events = parse_wire_events(text)

    report = evaluate_with_native_admission(
        config,
        events,
        max_shed_rate=args.max_shed_rate,
        cli_path=args.cli,
    )

    # Cross-check against the in-process Python reference for auditability.
    from tryops.native_admission import _python_fallback

    reference = _python_fallback(config, events, max_shed_rate=args.max_shed_rate)
    divergence = {
        key: {"native": report.get(key), "reference": reference.get(key)}
        for key in _COUNT_KEYS
        if report.get(key) != reference.get(key)
    }

    out = {
        "schema_version": "tryops.native_admission.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "wire": str(args.wire),
        "events": len(events),
        "config": {key: getattr(config, key) for key in (
            "bucket_capacity", "refill_per_sec", "max_concurrency",
            "breaker_window", "breaker_error_threshold",
            "breaker_cooldown_ms", "breaker_min_samples",
        )},
        "report": report,
        "reference_agrees": not divergence,
        "divergence": divergence,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    engine = report.get("engine", "unknown")
    print(
        f"[admission] engine={engine} events={len(events)} "
        f"admitted={report['admitted']} shed_rate={report['shed_rate']:.3f} "
        f"trips={report['breaker_trips']} recoveries={report['breaker_recoveries']} "
        f"final={report['final_breaker_state']} gate_ok={report['gate_ok']} "
        f"reference_agrees={not divergence}"
    )
    print(f"[admission] wrote {args.output}")

    if divergence:
        print(f"[admission] DIVERGENCE: {divergence}", file=sys.stderr)
        return 3
    return 0 if report.get("gate_ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
