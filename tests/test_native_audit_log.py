"""Tests for the native tamper-evident audit log bridge + native/reference
parity (hand-rolled C++ SHA-256 must equal hashlib)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_audit_log import (  # noqa: E402
    build_reference,
    chain_head,
    evaluate_with_native_audit_log,
    merkle_root,
    sha256_hex,
)

CLI = ROOT / "artifacts" / "native" / "tryops_audit_log_cli"


def test_sha256_reference():
    assert sha256_hex("abc") == hashlib.sha256(b"abc").hexdigest()


def test_merkle_root_stable_and_tamper_sensitive():
    payloads = [f"event-{i}" for i in range(5)]
    root = merkle_root(payloads)
    assert len(root) == 64
    assert merkle_root(payloads) == root  # deterministic
    mutated = list(payloads)
    mutated[2] += "X"
    assert merkle_root(mutated) != root  # tamper changes root


def test_single_and_empty():
    assert merkle_root([]) == sha256_hex("")
    assert merkle_root(["only"]) == sha256_hex("only")


def test_chain_head_progresses():
    assert chain_head([]) == ""
    h1 = chain_head(["a"])
    h2 = chain_head(["a", "b"])
    assert h1 != h2


@pytest.mark.skipif(not CLI.exists(), reason="native audit log CLI not built")
def test_native_matches_reference():
    payloads = [f"audit-record-{i} value={i*7}" for i in range(9)]
    native = evaluate_with_native_audit_log(payloads, prove_index=4, cli_path=CLI)
    reference = build_reference(payloads)
    assert native["engine"] == "native"
    # the hand-rolled C++ SHA-256 Merkle root must equal the hashlib reference
    assert native["merkle_root"] == reference["merkle_root"]
    assert native["chain_head"] == reference["chain_head"]
    assert native["chain_valid"] is True
    proof = native.get("proof")
    assert proof is not None
    assert proof["verified"] is True
    assert proof["index"] == 4
