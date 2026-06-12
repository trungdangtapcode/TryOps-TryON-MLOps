"""Tests for the native PII/secret redaction bridge + native/reference parity."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_redaction import (  # noqa: E402
    evaluate_with_native_redaction,
    fnv1a,
    luhn_valid,
    redact_text,
)

CLI = ROOT / "artifacts" / "native" / "tryops_redaction_cli"


def test_email_and_ip():
    r = redact_text("ping alice@example.com at 10.0.0.5 now")
    assert r["counts"]["email"] == 1
    assert r["counts"]["ipv4"] == 1
    assert "[REDACTED_EMAIL]" in r["redacted"]
    assert "alice@example.com" not in r["redacted"]


def test_secrets():
    r = redact_text(
        "sk-ABCDEFGHIJKLMNOPQRSTUVWX ghp_ABCDEFGHIJKLMNOPQRST AKIAIOSFODNN7EXAMPLE"
    )
    assert r["counts"]["api_key"] == 1
    assert r["counts"]["github_token"] == 1
    assert r["counts"]["aws_key"] == 1
    assert "AKIAIOSFODNN7EXAMPLE" not in r["redacted"]


def test_luhn_gate():
    assert luhn_valid("4111111111111111")
    assert not luhn_valid("4111111111111112")
    good = redact_text("card 4111 1111 1111 1111")
    assert good["counts"].get("credit_card") == 1
    bad = redact_text("id 1234567890123456")
    assert "credit_card" not in bad["counts"]


def test_clean_text_fingerprint_stable():
    r = redact_text("nothing sensitive here")
    assert r["total"] == 0
    assert r["input_fingerprint"] == r["output_fingerprint"]


def test_fnv1a_deterministic():
    assert fnv1a("abc") == fnv1a("abc")
    assert fnv1a("abc") != fnv1a("abd")


@pytest.mark.skipif(not CLI.exists(), reason="native redaction CLI not built")
def test_native_matches_reference():
    sample = ROOT / "samples" / "redaction" / "sensitive_log.txt"
    text = sample.read_text() if sample.exists() else (
        "alice@acme.com 4111 1111 1111 1111 sk-ABCDEFGHIJKLMNOPQRSTUV "
        "ghp_ABCDEFGHIJKLMNOPQRSTUV AKIAIOSFODNN7EXAMPLE 203.0.113.9 "
        "Bearer abcDEF0123456789ghIJKL eyJa.eyJb.sig-_X 123-45-6789"
    )
    native = evaluate_with_native_redaction(text, emit_redacted=True, cli_path=CLI)
    reference = redact_text(text)
    assert native["engine"] == "native"
    assert native["total"] == reference["total"], (native["counts"], reference["counts"])
    assert native["counts"] == reference["counts"]
    assert native["redacted"] == reference["redacted"]
    # fingerprints computed independently in C++ and Python must agree
    assert native["input_fingerprint"] == reference["input_fingerprint"]
    assert native["output_fingerprint"] == reference["output_fingerprint"]
