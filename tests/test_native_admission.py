"""Tests for the native admission controller bridge.

Verifies (a) the Python reference reimplementation produces the expected
admit/shed accounting, (b) the native binary and the reference agree bit-for-bit
when the binary is present, and (c) the wire round-trips.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_admission import (  # noqa: E402
    AdmissionConfig,
    RequestEvent,
    _python_fallback,
    evaluate_with_native_admission,
    parse_wire_events,
    serialize_wire,
)

CLI = ROOT / "artifacts" / "native" / "tryops_admission_cli"


def test_rate_limit_sheds_burst():
    config = AdmissionConfig(bucket_capacity=3, refill_per_sec=0, max_concurrency=100)
    events = [RequestEvent(ts_ms=0) for _ in range(10)]
    rep = _python_fallback(config, events, max_shed_rate=1.0)
    assert rep["admitted"] == 3
    assert rep["rejected_rate_limited"] == 7
    assert rep["admit_rate"] == pytest.approx(0.3)


def test_concurrency_bulkhead():
    config = AdmissionConfig(bucket_capacity=1000, refill_per_sec=1000, max_concurrency=2)
    events = [
        RequestEvent(ts_ms=0, duration_ms=100),
        RequestEvent(ts_ms=0, duration_ms=100),
        RequestEvent(ts_ms=0, duration_ms=100),  # shed: no slot
        RequestEvent(ts_ms=200, duration_ms=10),  # admitted after release
    ]
    rep = _python_fallback(config, events, max_shed_rate=1.0)
    assert rep["rejected_concurrency_full"] == 1
    assert rep["peak_inflight"] == 2
    assert rep["admitted"] == 3


def test_breaker_trips_and_recovers():
    config = AdmissionConfig(
        bucket_capacity=1000, refill_per_sec=1000, max_concurrency=1000,
        breaker_window=10, breaker_error_threshold=0.5,
        breaker_cooldown_ms=1000, breaker_min_samples=5,
    )
    events = [RequestEvent(ts_ms=i, outcome="error") for i in range(6)]
    events.append(RequestEvent(ts_ms=10, outcome="ok"))    # within cooldown -> shed
    events.append(RequestEvent(ts_ms=2000, outcome="ok"))  # half-open probe -> recover
    rep = _python_fallback(config, events, max_shed_rate=1.0)
    assert rep["breaker_trips"] >= 1
    assert rep["rejected_breaker_open"] >= 1
    assert rep["breaker_recoveries"] == 1
    assert rep["final_breaker_state"] == "closed"


def test_wire_roundtrip():
    config = AdmissionConfig(bucket_capacity=40, max_concurrency=8)
    events = [
        RequestEvent(ts_ms=0, cost=2, duration_ms=5, outcome="ok"),
        RequestEvent(ts_ms=7, cost=1, duration_ms=3, outcome="error"),
    ]
    wire = serialize_wire(config, events)
    parsed_config, parsed_events = parse_wire_events(wire)
    assert parsed_config.bucket_capacity == 40
    assert parsed_config.max_concurrency == 8
    assert len(parsed_events) == 2
    assert parsed_events[1].outcome == "error"
    assert parsed_events[0].cost == 2


@pytest.mark.skipif(not CLI.exists(), reason="native admission CLI not built")
def test_native_matches_reference():
    """The compiled C++ engine and the Python reference must agree exactly."""
    config = AdmissionConfig(
        bucket_capacity=40, refill_per_sec=200, max_concurrency=16,
        breaker_window=20, breaker_error_threshold=0.5,
        breaker_cooldown_ms=300, breaker_min_samples=8,
    )
    # deterministic mixed traffic
    events = []
    ts = 0
    for i in range(200):
        outcome = "error" if 60 <= i < 110 else "ok"
        events.append(RequestEvent(ts_ms=ts, cost=1, duration_ms=5, outcome=outcome))
        ts += 4
    native = evaluate_with_native_admission(config, events, max_shed_rate=0.7, cli_path=CLI)
    reference = _python_fallback(config, events, max_shed_rate=0.7)
    assert native["engine"] == "native"
    for key in (
        "total", "admitted", "rejected_rate_limited", "rejected_breaker_open",
        "rejected_concurrency_full", "breaker_trips", "breaker_recoveries",
        "peak_inflight", "final_breaker_state",
    ):
        assert native[key] == reference[key], f"mismatch on {key}"


def test_cli_end_to_end():
    """If the binary exists, run it on the committed sample and check JSON."""
    if not CLI.exists():
        pytest.skip("native admission CLI not built")
    wire = ROOT / "samples" / "admission" / "mixed_traffic.wire"
    if not wire.exists():
        pytest.skip("sample wire not generated")
    out = subprocess.run(
        [str(CLI), "--max-shed-rate", "0.7"],
        input=wire.read_text(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert out.stdout.strip().startswith("{")
    assert "final_breaker_state" in out.stdout
