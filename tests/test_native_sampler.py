"""Tests for the native trace sampler bridge + native/reference parity."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_sampler import (  # noqa: E402
    TraceItem,
    Xorshift64,
    evaluate_with_native_sampler,
    run_sampler_reference,
)

CLI = ROOT / "artifacts" / "native" / "tryops_sampler_cli"


def _items(n, every_priority=0):
    return [
        TraceItem(f"t-{i}", priority=(every_priority and i % every_priority == 0))
        for i in range(n)
    ]


def test_size_bounds():
    r = run_sampler_reference(_items(1000), capacity=50, seed=42)
    assert r["kept"] == 50
    small = run_sampler_reference(_items(10), capacity=50, seed=42)
    assert small["kept"] == 10


def test_determinism():
    a = run_sampler_reference(_items(5000), capacity=100, seed=123)
    b = run_sampler_reference(_items(5000), capacity=100, seed=123)
    c = run_sampler_reference(_items(5000), capacity=100, seed=999)
    assert a["sample"] == b["sample"]
    assert a["sample"] != c["sample"]


def test_priority_force_kept():
    r = run_sampler_reference(_items(1000, every_priority=100), capacity=50, seed=7, mode="priority")
    assert r["priority_kept"] == r["priority_seen"]
    assert r["sample"][0] == "t-0"
    assert r["kept"] == 50


def test_xorshift_deterministic():
    a = Xorshift64(12345)
    b = Xorshift64(12345)
    assert [a.next() for _ in range(5)] == [b.next() for _ in range(5)]


def test_uniformity():
    n, k, trials = 100, 10, 2000
    items = _items(n)
    counts = [0] * n
    for s in range(1, trials + 1):
        r = run_sampler_reference(items, capacity=k, seed=s * 2654435761)
        for sid in r["sample"]:
            counts[int(sid[2:])] += 1
    expected = trials * k / n
    off = sum(1 for c in counts if abs(c - expected) > 0.3 * expected)
    assert off <= n // 8


@pytest.mark.skipif(not CLI.exists(), reason="native sampler CLI not built")
@pytest.mark.parametrize("mode", ["reservoir", "priority"])
def test_native_matches_reference(mode):
    items = _items(3000, every_priority=97)
    native = evaluate_with_native_sampler(items, capacity=50, seed=20260612, mode=mode, cli_path=CLI)
    reference = run_sampler_reference(items, capacity=50, seed=20260612, mode=mode)
    assert native["engine"] == "native"
    assert native["sample"] == reference["sample"]
    assert native["priority_kept"] == reference["priority_kept"]
