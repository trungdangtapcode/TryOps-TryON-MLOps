"""Tests for the native HyperLogLog bridge + native/reference parity."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_hll import (  # noqa: E402
    HyperLogLog,
    evaluate_with_native_hll,
    hll_hash,
    run_hll_reference,
)

CLI = ROOT / "artifacts" / "native" / "tryops_hll_cli"


def test_accuracy():
    for true_n in (1000, 10000, 50000):
        r = run_hll_reference([f"u-{i}" for i in range(true_n)], precision=14)
        rel = abs(r["estimate"] - true_n) / true_n
        assert rel < 4 * r["standard_error"] + 0.01, (true_n, rel)


def test_duplicates_ignored():
    values = [f"k-{i}" for i in range(200)] * 50
    r = run_hll_reference(values, precision=12)
    assert abs(r["estimate"] - 200) / 200 < 0.12


def test_hash_deterministic():
    assert hll_hash("abc") == hll_hash("abc")
    assert hll_hash("abc") != hll_hash("abd")


def test_empty():
    assert run_hll_reference([], precision=10)["estimate"] < 1.0


def test_hll_object_matches_run():
    hll = HyperLogLog(12)
    for i in range(3000):
        hll.add(f"x{i}")
    direct = hll.estimate()
    via_run = run_hll_reference([f"x{i}" for i in range(3000)], precision=12)["estimate"]
    assert direct == via_run


@pytest.mark.skipif(not CLI.exists(), reason="native HLL CLI not built")
def test_native_matches_reference():
    sample = ROOT / "samples" / "hll" / "event_keys.txt"
    values = (
        [v for v in sample.read_text().splitlines() if v]
        if sample.exists()
        else [f"evt-{i % 4000}" for i in range(12000)]
    )
    native = evaluate_with_native_hll(values, precision=14, cli_path=CLI)
    reference = run_hll_reference(values, precision=14)
    assert native["engine"] == "native"
    assert native["observed"] == reference["observed"]
    assert native["registers"] == reference["registers"]
    # estimate agreement proves identical register state => identical hashing
    assert abs(native["estimate"] - reference["estimate"]) <= 1e-4 * reference["estimate"]
