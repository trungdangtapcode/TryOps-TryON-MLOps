#!/usr/bin/env python3
"""Run the native Bloom-filter dedup engine over a key stream and write an
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

from tryops.native_dedup import (  # noqa: E402
    evaluate_with_native_dedup,
    run_dedup_reference,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Native Bloom-filter dedup verdict.")
    parser.add_argument("--input", type=Path, default=Path("samples/dedup/idempotency_keys.txt"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/dedup/dedup_report.json"))
    parser.add_argument("--expected-items", type=int, default=5000)
    parser.add_argument("--target-fp-rate", type=float, default=0.01)
    parser.add_argument("--max-fp-rate", type=float, default=0.05)
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    keys = [line for line in args.input.read_text(encoding="utf-8").splitlines() if line]
    report = evaluate_with_native_dedup(
        keys,
        expected_items=args.expected_items,
        target_fp_rate=args.target_fp_rate,
        max_fp_rate=args.max_fp_rate,
        cli_path=args.cli,
    )
    reference = run_dedup_reference(
        keys, expected_items=args.expected_items, target_fp_rate=args.target_fp_rate
    )
    keys_count = len(set(keys))
    agrees = all(
        report.get(k) == reference.get(k)
        for k in ("total", "admitted", "rejected_dupe", "bits", "hashes", "set_bits")
    )

    out = {
        "schema_version": "tryops.native_dedup.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "input": str(args.input),
        "engine": report.get("engine"),
        "report": report,
        "true_unique_keys": keys_count,
        "reference_agrees": agrees,
        # admitted should equal true unique unless a false positive masked a key
        "false_positive_admits_blocked": keys_count - report.get("admitted", 0),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(
        f"[dedup] engine={report.get('engine')} total={report['total']} "
        f"admitted={report['admitted']} rejected_dupe={report['rejected_dupe']} "
        f"true_unique={keys_count} bits={report['bits']} k={report['hashes']} "
        f"fp_rate={report['theoretical_fp_rate']:.2e} reference_agrees={agrees}"
    )
    print(f"[dedup] wrote {args.output}")
    return 0 if (agrees and report.get("gate_ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
