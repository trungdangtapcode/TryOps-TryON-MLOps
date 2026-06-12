#!/usr/bin/env python3
"""Sample a trace stream with the native sampler and write an auditable report,
cross-checking the kept sample against the Python reference (bit-for-bit).
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

from tryops.native_sampler import (  # noqa: E402
    TraceItem,
    evaluate_with_native_sampler,
    run_sampler_reference,
)


def parse_wire(text: str):
    capacity, seed, mode = 100, 1, "reservoir"
    items = []
    for line in text.splitlines():
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key == "capacity":
            capacity = int(value)
        elif key == "seed":
            seed = int(value)
        elif key == "mode":
            mode = value
        elif key == "item":
            f = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
            items.append(TraceItem(f.get("id", ""), priority=f.get("priority") in ("1", "true")))
    return capacity, seed, mode, items


def main() -> int:
    parser = argparse.ArgumentParser(description="Native trace sampler verdict.")
    parser.add_argument("--wire", type=Path, default=Path("samples/sampler/trace_stream.wire"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/sampler/sampler_report.json"))
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    capacity, seed, mode, items = parse_wire(args.wire.read_text(encoding="utf-8"))
    report = evaluate_with_native_sampler(
        items, capacity=capacity, seed=seed, mode=mode, cli_path=args.cli
    )
    reference = run_sampler_reference(items, capacity=capacity, seed=seed, mode=mode)
    agrees = report.get("sample") == reference["sample"]

    out = {
        "schema_version": "tryops.native_sampler.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "wire": str(args.wire),
        "mode": mode,
        "seed": seed,
        "engine": report.get("engine"),
        "observed": report.get("observed"),
        "capacity": report.get("capacity"),
        "kept": report.get("kept"),
        "priority_seen": report.get("priority_seen"),
        "priority_kept": report.get("priority_kept"),
        "reference_sample_agrees": agrees,
        "sample_preview": (report.get("sample") or [])[:20],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(
        f"[sampler] engine={report.get('engine')} mode={mode} observed={report.get('observed')} "
        f"kept={report.get('kept')}/{report.get('capacity')} "
        f"priority_seen={report.get('priority_seen')} priority_kept={report.get('priority_kept')} "
        f"reference_agrees={agrees}"
    )
    print(f"[sampler] wrote {args.output}")
    return 0 if agrees else 2


if __name__ == "__main__":
    raise SystemExit(main())
