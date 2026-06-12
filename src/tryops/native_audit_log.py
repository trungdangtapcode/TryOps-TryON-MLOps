"""Bridge to the native C++ tamper-evident audit log (SHA-256 Merkle tree +
hash chain).

The native engine implements SHA-256 from scratch; this module's reference path
uses the standard-library ``hashlib`` so the test suite can confirm the
hand-rolled C++ digest matches the reference bit-for-bit. If the binary is
absent, the reference computes the same root/chain so offline runs still work.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_AUDIT_CLI = Path("artifacts/native/tryops_audit_log_cli")


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def merkle_root(payloads: Sequence[str]) -> str:
    """RFC-6962-style Merkle root with odd-node duplication, matching the C++
    engine (leaves are sha256(payload); empty tree is sha256(''))."""
    if not payloads:
        return sha256_hex("")
    level = [sha256_hex(p) for p in payloads]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(sha256_hex(left + right))
        level = nxt
    return level[0]


def chain_head(payloads: Sequence[str]) -> str:
    head = ""
    for p in payloads:
        head = sha256_hex(head + sha256_hex(p))
    return head


def build_reference(payloads: Sequence[str]) -> dict[str, Any]:
    return {
        "size": len(payloads),
        "merkle_root": merkle_root(payloads),
        "chain_head": chain_head(payloads),
        "chain_valid": True,
    }


def evaluate_with_native_audit_log(
    payloads: Sequence[str],
    *,
    prove_index: int | None = None,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(
        cli_path or os.environ.get("TRYOPS_NATIVE_AUDIT_CLI", DEFAULT_NATIVE_AUDIT_CLI)
    )
    stdin = "\n".join(payloads) + ("\n" if payloads else "")
    if path.exists():
        args = [str(path)]
        if prove_index is not None:
            args += ["--prove", str(prove_index)]
        completed = subprocess.run(
            args, input=stdin, text=True, capture_output=True, check=False
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            return report

    report = build_reference(payloads)
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report
