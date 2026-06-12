"""Tests for the native retry policy bridge + native/reference parity."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_retry import (  # noqa: E402
    RetryConfig,
    Xorshift64,
    backoff_for,
    evaluate_with_native_retry,
    run_retry_reference,
)

CLI = ROOT / "artifacts" / "native" / "tryops_retry_cli"


def test_recovery():
    cfg = RetryConfig(jitter="none", retry_budget_ratio=100.0)
    r = run_retry_reference([2] * 100, cfg)
    assert r["successes"] == 100
    assert r["retries_attempted"] == 100
    assert r["success_rate_without_retry"] == 0.0


def test_exhaustion():
    cfg = RetryConfig(jitter="none", retry_budget_ratio=100.0, max_retries=3)
    r = run_retry_reference([10] * 10, cfg)
    assert r["failures"] == 10
    assert r["retries_exhausted"] == 10
    assert r["retries_attempted"] == 30


def test_budget_caps_storm():
    cfg = RetryConfig(jitter="none", retry_budget_ratio=0.1)
    r = run_retry_reference([2] * 100, cfg)
    assert r["retries_attempted"] <= 11
    assert r["retries_denied_budget"] > 0
    assert r["successes"] < 100


def test_backoff_growth_and_jitter_bounds():
    cfg = RetryConfig(jitter="none", base_backoff_ms=50, max_backoff_ms=2000)
    rng = Xorshift64(1)
    assert backoff_for(cfg, 0, rng) == 50
    assert backoff_for(cfg, 1, rng) == 100
    assert backoff_for(cfg, 2, rng) == 200
    cfg.jitter = "full"
    rng = Xorshift64(7)
    for _ in range(500):
        b = backoff_for(cfg, 1, rng)
        assert 0.0 <= b < 100.0 + 1e-9


@pytest.mark.skipif(not CLI.exists(), reason="native retry CLI not built")
def test_native_matches_reference():
    cfg = RetryConfig(jitter="full", retry_budget_ratio=0.2, seed=99)
    needs = [2 if i % 3 == 0 else (5 if i % 17 == 0 else 1) for i in range(1000)]
    native = evaluate_with_native_retry(needs, cfg, min_success_rate=0.0, cli_path=CLI)
    reference = run_retry_reference(needs, cfg)
    assert native["engine"] == "native"
    for key in (
        "requests", "successes", "failures", "retries_attempted",
        "retries_denied_budget", "retries_exhausted",
    ):
        assert native[key] == reference[key], f"mismatch on {key}"
    # jittered backoff sum reproducible across C++/Python
    assert abs(native["total_backoff_ms"] - reference["total_backoff_ms"]) < 1e-3
