#!/usr/bin/env python3
"""Redact PII/secrets from a sample text using the native C++ engine and write
an auditable report. Cross-checks native counts against the Python reference.
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

from tryops.native_redaction import (  # noqa: E402
    evaluate_with_native_redaction,
    redact_text,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Native PII/secret redaction verdict.")
    parser.add_argument("--input", type=Path, default=Path("samples/redaction/sensitive_log.txt"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/redaction/redaction_report.json"))
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    report = evaluate_with_native_redaction(text, emit_redacted=True, cli_path=args.cli)
    reference = redact_text(text)

    # native may omit per-call extras; compare the counts + redacted body.
    agrees = (
        report.get("total") == reference["total"]
        and report.get("counts") == reference["counts"]
        and report.get("redacted") == reference["redacted"]
    )

    out = {
        "schema_version": "tryops.native_redaction.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "input": str(args.input),
        "engine": report.get("engine"),
        "total_redactions": report.get("total"),
        "counts": report.get("counts"),
        "input_fingerprint": report.get("input_fingerprint"),
        "output_fingerprint": report.get("output_fingerprint"),
        "reference_agrees": agrees,
        # NB: do NOT store the raw input; only the redacted body is safe to keep.
        "redacted_preview": (report.get("redacted") or "")[:500],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(
        f"[redaction] engine={report.get('engine')} total={report.get('total')} "
        f"counts={report.get('counts')} reference_agrees={agrees}"
    )
    print(f"[redaction] wrote {args.output}")
    return 0 if agrees else 3


if __name__ == "__main__":
    raise SystemExit(main())
