#!/usr/bin/env python3
"""Build a tamper-evident audit log from a sample event stream using the native
C++ engine, emit the Merkle root + an inclusion proof, and cross-check the root
and chain head against the hashlib reference. Also demonstrates tamper detection
by mutating one entry and confirming the root changes.
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

from tryops.native_audit_log import (  # noqa: E402
    build_reference,
    evaluate_with_native_audit_log,
    merkle_root,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Native tamper-evident audit log.")
    parser.add_argument("--input", type=Path, default=Path("samples/audit/events.log"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/audit/audit_log_report.json"))
    parser.add_argument("--prove", type=int, default=0)
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    payloads = [
        line for line in args.input.read_text(encoding="utf-8").splitlines() if line
    ]
    report = evaluate_with_native_audit_log(
        payloads, prove_index=args.prove, cli_path=args.cli
    )
    reference = build_reference(payloads)

    root_agrees = report.get("merkle_root") == reference["merkle_root"]
    chain_agrees = report.get("chain_head") == reference["chain_head"]

    # Tamper demonstration: flip one entry, confirm the root diverges.
    tampered = list(payloads)
    if tampered:
        tampered[len(tampered) // 2] += "::TAMPERED"
    tamper_detected = merkle_root(tampered) != reference["merkle_root"]

    out = {
        "schema_version": "tryops.native_audit_log.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "input": str(args.input),
        "engine": report.get("engine"),
        "size": report.get("size"),
        "merkle_root": report.get("merkle_root"),
        "chain_head": report.get("chain_head"),
        "chain_valid": report.get("chain_valid"),
        "inclusion_proof": report.get("proof"),
        "reference_root_agrees": root_agrees,
        "reference_chain_agrees": chain_agrees,
        "tamper_detected": tamper_detected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    proof = report.get("proof") or {}
    print(
        f"[audit] engine={report.get('engine')} size={report.get('size')} "
        f"root={str(report.get('merkle_root'))[:16]}... chain_valid={report.get('chain_valid')} "
        f"proof_verified={proof.get('verified')} root_agrees={root_agrees} "
        f"chain_agrees={chain_agrees} tamper_detected={tamper_detected}"
    )
    print(f"[audit] wrote {args.output}")
    ok = root_agrees and chain_agrees and tamper_detected and report.get("chain_valid")
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
