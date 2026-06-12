#!/usr/bin/env python3
"""Estimate distinct-value cardinality with the native HyperLogLog engine and
write an auditable report. Cross-checks the native estimate against the Python
reference and against the exact ground-truth distinct count.
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

from tryops.native_hll import (  # noqa: E402
    evaluate_with_native_hll,
    run_hll_reference,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Native HyperLogLog cardinality.")
    parser.add_argument("--input", type=Path, default=Path("samples/hll/event_keys.txt"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/hll/hll_report.json"))
    parser.add_argument("--precision", type=int, default=14)
    parser.add_argument("--max-rel-error", type=float, default=0.05)
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    values = [line for line in args.input.read_text(encoding="utf-8").splitlines() if line]
    report = evaluate_with_native_hll(values, precision=args.precision, cli_path=args.cli)
    reference = run_hll_reference(values, precision=args.precision)

    true_distinct = len(set(values))
    est = float(report.get("estimate", 0.0))
    rel_error = abs(est - true_distinct) / true_distinct if true_distinct else 0.0
    # estimate match proves register/hash parity between C++ and Python
    estimates_agree = abs(est - reference["estimate"]) <= 1e-6 * max(1.0, reference["estimate"])

    out = {
        "schema_version": "tryops.native_hll.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "input": str(args.input),
        "engine": report.get("engine"),
        "precision": report.get("precision"),
        "registers": report.get("registers"),
        "observed": report.get("observed"),
        "estimate": est,
        "true_distinct": true_distinct,
        "relative_error": rel_error,
        "theoretical_standard_error": report.get("standard_error"),
        "reference_estimates_agree": estimates_agree,
        "within_error_budget": rel_error <= args.max_rel_error,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(
        f"[hll] engine={report.get('engine')} observed={report.get('observed')} "
        f"estimate={est:.0f} true={true_distinct} rel_error={rel_error:.4f} "
        f"std_err={report.get('standard_error'):.4f} "
        f"reference_agrees={estimates_agree}"
    )
    print(f"[hll] wrote {args.output}")
    return 0 if (estimates_agree and rel_error <= args.max_rel_error) else 2


if __name__ == "__main__":
    raise SystemExit(main())
