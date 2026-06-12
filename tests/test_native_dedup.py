"""Tests for the native Bloom-filter dedup bridge + native/reference parity."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_dedup import (  # noqa: E402
    BloomFilter,
    evaluate_with_native_dedup,
    optimal_bits,
    optimal_hashes,
    run_dedup_reference,
)

CLI = ROOT / "artifacts" / "native" / "tryops_dedup_cli"


def test_no_false_negatives():
    f = BloomFilter(1000, 0.01)
    for i in range(500):
        f.insert_if_absent(f"k-{i}")
    assert all(f.maybe_contains(f"k-{i}") for i in range(500))


def test_dedup_counts():
    keys = [f"req-{i}" for i in range(300)] * 2
    r = run_dedup_reference(keys, expected_items=2000, target_fp_rate=0.01)
    assert r["total"] == 600
    assert r["admitted"] <= 300
    assert r["admitted"] >= 297  # at most a couple false positives
    assert r["rejected_dupe"] == r["total"] - r["admitted"]


def test_sizing_math():
    assert optimal_bits(1000, 0.0001) > optimal_bits(1000, 0.01)
    assert optimal_bits(100000, 0.01) > optimal_bits(1000, 0.01)
    assert optimal_hashes(optimal_bits(1000, 0.01), 1000) >= 1


@pytest.mark.skipif(not CLI.exists(), reason="native dedup CLI not built")
def test_native_matches_reference():
    sample = ROOT / "samples" / "dedup" / "idempotency_keys.txt"
    keys = (
        [k for k in sample.read_text().splitlines() if k]
        if sample.exists()
        else ([f"req-{i}" for i in range(200)] * 2)
    )
    native = evaluate_with_native_dedup(
        keys, expected_items=5000, target_fp_rate=0.01, max_fp_rate=0.05, cli_path=CLI
    )
    reference = run_dedup_reference(keys, expected_items=5000, target_fp_rate=0.01)
    assert native["engine"] == "native"
    for key in ("total", "admitted", "rejected_dupe", "bits", "hashes", "set_bits"):
        assert native[key] == reference[key], f"mismatch on {key}"
