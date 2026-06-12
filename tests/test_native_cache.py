"""Tests for the native LRU+TTL cache bridge + native/reference parity."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_cache import (  # noqa: E402
    CacheConfig,
    evaluate_with_native_cache,
    parse_cache_wire,
    run_cache_reference,
)

CLI = ROOT / "artifacts" / "native" / "tryops_cache_cli"


def test_basic_hits():
    r = run_cache_reference([(0, "a"), (1, "a"), (2, "a")], CacheConfig(10, 1000))
    assert r["hits"] == 2
    assert r["misses"] == 1


def test_lru_eviction():
    events = [(0, "a"), (1, "b"), (2, "c"), (3, "a")]
    r = run_cache_reference(events, CacheConfig(capacity=2, ttl_ms=100000))
    assert r["evictions"] >= 2
    assert r["hits"] == 0  # a evicted before re-access


def test_ttl_expiry():
    events = [(0, "k"), (50, "k"), (1000, "k")]
    r = run_cache_reference(events, CacheConfig(capacity=10, ttl_ms=100))
    assert r["expirations"] >= 1


def test_recency_protects():
    events = [(0, "a"), (1, "b"), (2, "a"), (3, "c"), (4, "a")]
    r = run_cache_reference(events, CacheConfig(capacity=2, ttl_ms=100000))
    assert r["hits"] >= 2  # a hit at t=2 and t=4


def test_wire_roundtrip():
    cfg, events = parse_cache_wire(
        "capacity=8\nttl_ms=500\nevent=ts_ms=0;key=x\nevent=ts_ms=3;key=y\n"
    )
    assert cfg.capacity == 8 and cfg.ttl_ms == 500
    assert events == [(0, "x"), (3, "y")]


@pytest.mark.skipif(not CLI.exists(), reason="native cache CLI not built")
def test_native_matches_reference():
    sample = ROOT / "samples" / "cache" / "requests.wire"
    if sample.exists():
        config, events = parse_cache_wire(sample.read_text())
    else:
        config = CacheConfig(capacity=64, ttl_ms=100000)
        events = [(i, f"k-{i % 200}") for i in range(2000)]
    native = evaluate_with_native_cache(events, config, min_hit_rate=0.0, cli_path=CLI)
    reference = run_cache_reference(events, config)
    assert native["engine"] == "native"
    for key in ("total", "hits", "misses", "evictions", "expirations", "final_size"):
        assert native[key] == reference[key], f"mismatch on {key}"
