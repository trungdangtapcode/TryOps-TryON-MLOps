"""Bridge to the native C++ trace sampler (reservoir + priority modes).

The Python reference replicates the xorshift64* RNG and the sampling algorithms
exactly, so given the same seed the C++ engine and the reference select the
identical sample (verified in tests).
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_SAMPLER_CLI = Path("artifacts/native/tryops_sampler_cli")

_MASK = (1 << 64) - 1


class Xorshift64:
    def __init__(self, seed: int) -> None:
        self.state = seed if seed else 0x9E3779B97F4A7C15

    def next(self) -> int:
        x = self.state
        x ^= x >> 12
        x = (x ^ (x << 25)) & _MASK
        x ^= x >> 27
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & _MASK

    def below(self, bound: int) -> int:
        return self.next() % bound if bound else 0


@dataclass
class TraceItem:
    id: str
    priority: bool = False


def reservoir_sample(items: Sequence[TraceItem], capacity: int, seed: int) -> dict[str, Any]:
    rng = Xorshift64(seed)
    sample: list[str] = []
    observed = priority_seen = 0
    for i, it in enumerate(items):
        observed += 1
        if it.priority:
            priority_seen += 1
        if len(sample) < capacity:
            sample.append(it.id)
        else:
            j = rng.below(i + 1)
            if j < capacity:
                sample[j] = it.id
    return {
        "observed": observed, "capacity": capacity, "kept": len(sample),
        "priority_seen": priority_seen, "priority_kept": 0, "sample": sample,
    }


def priority_sample(items: Sequence[TraceItem], capacity: int, seed: int) -> dict[str, Any]:
    rng = Xorshift64(seed)
    kept: list[str] = []
    rest: list[TraceItem] = []
    observed = priority_seen = priority_kept = 0
    for it in items:
        observed += 1
        if it.priority:
            priority_seen += 1
            if len(kept) < capacity:
                kept.append(it.id)
                priority_kept += 1
        else:
            rest.append(it)
    remaining = capacity - len(kept)
    filler: list[str] = []
    for i, it in enumerate(rest):
        if len(filler) < remaining:
            filler.append(it.id)
        elif remaining > 0:
            j = rng.below(i + 1)
            if j < remaining:
                filler[j] = it.id
    sample = kept + filler
    return {
        "observed": observed, "capacity": capacity, "kept": len(sample),
        "priority_seen": priority_seen, "priority_kept": priority_kept, "sample": sample,
    }


def run_sampler_reference(
    items: Sequence[TraceItem], *, capacity: int, seed: int, mode: str = "reservoir"
) -> dict[str, Any]:
    if mode == "priority":
        return priority_sample(items, capacity, seed)
    return reservoir_sample(items, capacity, seed)


def _serialize(items: Sequence[TraceItem], capacity: int, seed: int, mode: str) -> str:
    lines = [f"capacity={capacity}", f"seed={seed}", f"mode={mode}"]
    lines += [f"item=id={it.id};priority={1 if it.priority else 0}" for it in items]
    return "\n".join(lines) + "\n"


def evaluate_with_native_sampler(
    items: Sequence[TraceItem],
    *,
    capacity: int = 100,
    seed: int = 1,
    mode: str = "reservoir",
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_SAMPLER_CLI", DEFAULT_NATIVE_SAMPLER_CLI))
    if path.exists():
        completed = subprocess.run(
            [str(path)], input=_serialize(items, capacity, seed, mode),
            text=True, capture_output=True, check=False,
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            return report

    report = run_sampler_reference(items, capacity=capacity, seed=seed, mode=mode)
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report
