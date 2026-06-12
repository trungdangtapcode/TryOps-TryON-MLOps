#!/usr/bin/env python3
"""Run the native LRU+TTL response cache over a request key stream and write an
auditable report, cross-checking native counts against the Python reference.
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

from tryops.native_cache import (  # noqa: E402
    evaluate_with_native_cache,
    parse_cache_wire,
    run_cache_reference,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Native LRU+TTL cache verdict.")
    parser.add_argument("--wire", type=Path, default=Path("samples/cache/requests.wire"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/cache/cache_report.json"))
    parser.add_argument("--min-hit-rate", type=float, default=0.5)
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    config, events = parse_cache_wire(args.wire.read_text(encoding="utf-8"))
    report = evaluate_with_native_cache(
        events, config, min_hit_rate=args.min_hit_rate, cli_path=args.cli
    )
    reference = run_cache_reference(events, config)
    agrees = all(
        report.get(k) == reference.get(k)
        for k in ("total", "hits", "misses", "evictions", "expirations", "final_size")
    )

    out = {
        "schema_version": "tryops.native_cache.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "wire": str(args.wire),
        "config": {"capacity": config.capacity, "ttl_ms": config.ttl_ms},
        "engine": report.get("engine"),
        "report": report,
        "reference_agrees": agrees,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(
        f"[cache] engine={report.get('engine')} total={report['total']} "
        f"hits={report['hits']} misses={report['misses']} "
        f"hit_rate={report['hit_rate']:.3f} evictions={report['evictions']} "
        f"expirations={report['expirations']} reference_agrees={agrees}"
    )
    print(f"[cache] wrote {args.output}")
    return 0 if (agrees and report.get("gate_ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
