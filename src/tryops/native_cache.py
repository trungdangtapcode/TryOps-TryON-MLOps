"""Bridge to the native C++ LRU+TTL response cache.

The Python reference reproduces the exact LRU + sliding-TTL semantics of the C++
engine (insertion order, eviction, expiry) so the two agree bit-for-bit on hits,
misses, evictions and expirations.
"""
from __future__ import annotations

import json
import os
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_NATIVE_CACHE_CLI = Path("artifacts/native/tryops_cache_cli")


@dataclass
class CacheConfig:
    capacity: int = 1024
    ttl_ms: int = 60000


def run_cache_reference(
    events: Sequence[tuple[int, str]], config: CacheConfig
) -> dict[str, Any]:
    cap = max(1, config.capacity)
    store: "OrderedDict[str, int]" = OrderedDict()  # key -> expire_at
    total = hits = misses = evictions = expirations = 0
    for ts, key in events:
        total += 1
        if key in store:
            if store[key] > ts:
                hits += 1
                store[key] = ts + config.ttl_ms  # sliding TTL
                store.move_to_end(key, last=False)  # MRU at front
                continue
            expirations += 1
            del store[key]
        misses += 1
        if len(store) >= cap:
            store.popitem(last=True)  # evict LRU (tail)
            evictions += 1
        store[key] = ts + config.ttl_ms
        store.move_to_end(key, last=False)
    return {
        "total": total,
        "hits": hits,
        "misses": misses,
        "evictions": evictions,
        "expirations": expirations,
        "final_size": len(store),
        "hit_rate": hits / total if total else 0.0,
    }


def _serialize(events: Iterable[tuple[int, str]], config: CacheConfig) -> str:
    lines = [f"capacity={config.capacity}", f"ttl_ms={config.ttl_ms}"]
    lines += [f"event=ts_ms={ts};key={key}" for ts, key in events]
    return "\n".join(lines) + "\n"


def evaluate_with_native_cache(
    events: Sequence[tuple[int, str]],
    config: CacheConfig,
    *,
    min_hit_rate: float = 0.0,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(
        cli_path or os.environ.get("TRYOPS_NATIVE_CACHE_CLI", DEFAULT_NATIVE_CACHE_CLI)
    )
    if path.exists():
        completed = subprocess.run(
            [str(path), "--min-hit-rate", str(min_hit_rate)],
            input=_serialize(events, config),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            return report

    report = run_cache_reference(events, config)
    report["min_hit_rate"] = min_hit_rate
    report["gate_ok"] = report["hit_rate"] >= min_hit_rate
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report


def parse_cache_wire(text: str) -> tuple[CacheConfig, list[tuple[int, str]]]:
    config = CacheConfig()
    events: list[tuple[int, str]] = []
    for line in text.splitlines():
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key == "capacity":
            config.capacity = int(value)
        elif key == "ttl_ms":
            config.ttl_ms = int(value)
        elif key == "event":
            fields = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
            events.append((int(fields.get("ts_ms", 0)), fields.get("key", "")))
    return config, events
