"""Bridge to the native C++ admission controller (token bucket + circuit
breaker + concurrency bulkhead).

The hot-path decision logic lives in ``native/cpp/tryops_admission`` and runs as
a compiled binary on the production boundary. This module serialises an event
stream to the wire protocol, invokes the CLI, and parses the JSON report. If the
binary is unavailable it falls back to a pure-Python reimplementation so offline
``make smoke`` still works — but the native verdict is what ships.
"""
from __future__ import annotations

import json
import os
import subprocess
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_NATIVE_ADMISSION_CLI = Path("artifacts/native/tryops_admission_cli")

_CONFIG_KEYS = (
    "bucket_capacity",
    "refill_per_sec",
    "max_concurrency",
    "breaker_window",
    "breaker_error_threshold",
    "breaker_cooldown_ms",
    "breaker_min_samples",
)


@dataclass
class AdmissionConfig:
    bucket_capacity: float = 100.0
    refill_per_sec: float = 50.0
    max_concurrency: int = 32
    breaker_window: int = 20
    breaker_error_threshold: float = 0.5
    breaker_cooldown_ms: int = 1000
    breaker_min_samples: int = 5

    def wire_lines(self) -> list[str]:
        return [f"{key}={getattr(self, key)}" for key in _CONFIG_KEYS]


@dataclass
class RequestEvent:
    ts_ms: int
    cost: float = 1.0
    duration_ms: int = 0
    outcome: str = "ok"

    def wire(self) -> str:
        return (
            f"event=ts_ms={int(self.ts_ms)};cost={self.cost};"
            f"duration_ms={int(self.duration_ms)};outcome={self.outcome}"
        )


def serialize_wire(config: AdmissionConfig, events: Iterable[RequestEvent]) -> str:
    lines = config.wire_lines()
    lines.extend(event.wire() for event in events)
    return "\n".join(lines) + "\n"


def evaluate_with_native_admission(
    config: AdmissionConfig,
    events: Iterable[RequestEvent],
    *,
    max_shed_rate: float = 1.0,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the admission controller. Returns the report dict plus an
    ``engine`` field indicating whether the native binary or the Python
    fallback produced it."""
    events = list(events)
    path = Path(
        cli_path
        or os.environ.get("TRYOPS_NATIVE_ADMISSION_CLI", DEFAULT_NATIVE_ADMISSION_CLI)
    )
    wire = serialize_wire(config, events)

    if path.exists():
        completed = subprocess.run(
            [str(path), "--max-shed-rate", str(max_shed_rate)],
            input=wire,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            report["exit_code"] = completed.returncode
            return report

    report = _python_fallback(config, events, max_shed_rate=max_shed_rate)
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report


@dataclass
class _State:
    tokens: float
    last_refill_ms: int = 0
    started: bool = False
    inflight: deque = field(default_factory=deque)
    breaker_state: str = "closed"
    breaker_opened_ms: int = 0
    window: deque = field(default_factory=deque)
    errors: int = 0


def _python_fallback(
    config: AdmissionConfig,
    events: list[RequestEvent],
    *,
    max_shed_rate: float,
) -> dict[str, Any]:
    """Reference reimplementation mirroring tryops_admission.cpp exactly so the
    offline path and the native path agree bit-for-bit on counts."""
    s = _State(tokens=config.bucket_capacity)
    rep = {
        "total": 0,
        "admitted": 0,
        "rejected_rate_limited": 0,
        "rejected_breaker_open": 0,
        "rejected_concurrency_full": 0,
        "breaker_trips": 0,
        "breaker_recoveries": 0,
        "peak_inflight": 0,
        "min_tokens": config.bucket_capacity,
    }
    admitted_errors = 0

    def err_rate() -> float:
        return s.errors / len(s.window) if s.window else 0.0

    for ev in events:
        rep["total"] += 1
        # refill
        if not s.started:
            s.last_refill_ms = ev.ts_ms
            s.started = True
        elif ev.ts_ms > s.last_refill_ms:
            elapsed = (ev.ts_ms - s.last_refill_ms) / 1000.0
            s.tokens = min(config.bucket_capacity, s.tokens + elapsed * config.refill_per_sec)
            s.last_refill_ms = ev.ts_ms
        # release finished
        while s.inflight and s.inflight[0] <= ev.ts_ms:
            s.inflight.popleft()

        # breaker gate
        if s.breaker_state == "open":
            if ev.ts_ms - s.breaker_opened_ms >= config.breaker_cooldown_ms:
                s.breaker_state = "half_open"
            else:
                rep["rejected_breaker_open"] += 1
                continue
        # concurrency
        if len(s.inflight) >= config.max_concurrency:
            rep["rejected_concurrency_full"] += 1
            continue
        # token bucket
        if s.tokens < ev.cost:
            rep["rejected_rate_limited"] += 1
            rep["min_tokens"] = min(rep["min_tokens"], s.tokens)
            continue

        # admit
        s.tokens -= ev.cost
        rep["min_tokens"] = min(rep["min_tokens"], s.tokens)
        s.inflight.append(ev.ts_ms + max(0, ev.duration_ms))
        rep["peak_inflight"] = max(rep["peak_inflight"], len(s.inflight))
        rep["admitted"] += 1
        if ev.outcome == "error":
            admitted_errors += 1

        is_err = 1 if ev.outcome == "error" else 0
        s.window.append(is_err)
        s.errors += is_err
        while len(s.window) > config.breaker_window:
            s.errors -= s.window.popleft()

        if s.breaker_state == "half_open":
            if ev.outcome == "error":
                s.breaker_state = "open"
                s.breaker_opened_ms = ev.ts_ms
                rep["breaker_trips"] += 1
            else:
                s.breaker_state = "closed"
                rep["breaker_recoveries"] += 1
                s.window.clear()
                s.errors = 0
        elif s.breaker_state == "closed":
            if len(s.window) >= config.breaker_min_samples and err_rate() >= config.breaker_error_threshold:
                s.breaker_state = "open"
                s.breaker_opened_ms = ev.ts_ms
                rep["breaker_trips"] += 1

    total = rep["total"]
    rep["admit_rate"] = rep["admitted"] / total if total else 0.0
    rep["shed_rate"] = 1.0 - rep["admit_rate"]
    rep["observed_error_rate"] = admitted_errors / rep["admitted"] if rep["admitted"] else 0.0
    rep["final_breaker_state"] = s.breaker_state
    rep["max_shed_rate"] = max_shed_rate
    rep["gate_ok"] = s.breaker_state == "closed" and rep["shed_rate"] <= max_shed_rate
    return rep


def parse_wire_events(text: str) -> tuple[AdmissionConfig, list[RequestEvent]]:
    """Parse a `.wire` file back into a config + events (for replay/tests)."""
    config = AdmissionConfig()
    events: list[RequestEvent] = []
    for line in text.splitlines():
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key in _CONFIG_KEYS:
            current = getattr(config, key)
            setattr(config, key, type(current)(float(value)) if isinstance(current, int) else float(value))
        elif key == "event":
            fields: Mapping[str, str] = dict(
                part.split("=", 1) for part in value.split(";") if "=" in part
            )
            events.append(
                RequestEvent(
                    ts_ms=int(float(fields.get("ts_ms", 0))),
                    cost=float(fields.get("cost", 1.0)),
                    duration_ms=int(float(fields.get("duration_ms", 0))),
                    outcome=fields.get("outcome", "ok"),
                )
            )
    return config, events
