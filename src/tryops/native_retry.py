"""Bridge to the native C++ retry policy engine (backoff + jitter + budget).

The Python reference replicates the xorshift64 RNG and retry/backoff/budget logic
exactly, so the simulated outcomes and accumulated backoff agree with the native
binary (jittered delays are reproducible given a seed).
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_RETRY_CLI = Path("artifacts/native/tryops_retry_cli")

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

    def unit(self) -> float:
        return (self.next() >> 11) * (1.0 / 9007199254740992.0)


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_backoff_ms: float = 50.0
    max_backoff_ms: float = 2000.0
    jitter: str = "full"  # full|equal|none
    retry_budget_ratio: float = 0.2
    seed: int = 1


def backoff_for(cfg: RetryConfig, retry_index: int, rng: Xorshift64) -> float:
    exp = min(cfg.base_backoff_ms * (2.0 ** retry_index), cfg.max_backoff_ms)
    if cfg.jitter == "none":
        return exp
    if cfg.jitter == "equal":
        return exp / 2.0 + rng.unit() * (exp / 2.0)
    return rng.unit() * exp  # full


def run_retry_reference(attempts_needed: Sequence[int], cfg: RetryConfig) -> dict[str, Any]:
    rng = Xorshift64(cfg.seed)
    rep = {
        "requests": 0, "successes": 0, "failures": 0,
        "retries_attempted": 0, "retries_denied_budget": 0,
        "retries_exhausted": 0, "total_backoff_ms": 0.0,
    }
    first_try = 0
    for need in attempts_needed:
        rep["requests"] += 1
        if need <= 1:
            first_try += 1
        attempt = 1
        succeeded = False
        while True:
            if attempt >= need:
                succeeded = True
                break
            if attempt > cfg.max_retries:
                rep["retries_exhausted"] += 1
                break
            allowed = math.floor(rep["requests"] * cfg.retry_budget_ratio)
            if rep["retries_attempted"] >= allowed:
                rep["retries_denied_budget"] += 1
                break
            rep["total_backoff_ms"] += backoff_for(cfg, attempt - 1, rng)
            rep["retries_attempted"] += 1
            attempt += 1
        if succeeded:
            rep["successes"] += 1
        else:
            rep["failures"] += 1
    n = rep["requests"]
    rep["success_rate"] = rep["successes"] / n if n else 0.0
    rep["success_rate_without_retry"] = first_try / n if n else 0.0
    return rep


def _serialize(attempts_needed: Sequence[int], cfg: RetryConfig) -> str:
    lines = [
        f"max_retries={cfg.max_retries}",
        f"base_backoff_ms={cfg.base_backoff_ms}",
        f"max_backoff_ms={cfg.max_backoff_ms}",
        f"jitter={cfg.jitter}",
        f"retry_budget_ratio={cfg.retry_budget_ratio}",
        f"seed={cfg.seed}",
    ]
    lines += [f"request=attempts_needed={n}" for n in attempts_needed]
    return "\n".join(lines) + "\n"


def evaluate_with_native_retry(
    attempts_needed: Sequence[int],
    cfg: RetryConfig,
    *,
    min_success_rate: float = 0.0,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_RETRY_CLI", DEFAULT_NATIVE_RETRY_CLI))
    if path.exists():
        completed = subprocess.run(
            [str(path), "--min-success-rate", str(min_success_rate)],
            input=_serialize(attempts_needed, cfg),
            text=True, capture_output=True, check=False,
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            return report

    report = run_retry_reference(attempts_needed, cfg)
    report["min_success_rate"] = min_success_rate
    report["gate_ok"] = report["success_rate"] >= min_success_rate
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report
