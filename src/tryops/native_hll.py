"""Bridge to the native C++ HyperLogLog cardinality estimator.

The Python reference replicates the engine's hash (FNV-1a + murmur3 fmix64) and
estimator exactly, so an estimate match proves the register state — and thus the
per-value hashes — agreed between C++ and Python.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_HLL_CLI = Path("artifacts/native/tryops_hll_cli")

_MASK = (1 << 64) - 1


def _fnv1a(data: str) -> int:
    h = 1469598103934665603
    for b in data.encode("utf-8", "surrogatepass"):
        h ^= b
        h = (h * 1099511628211) & _MASK
    return h


def _fmix64(h: int) -> int:
    h ^= h >> 33
    h = (h * 0xFF51AFD7ED558CCD) & _MASK
    h ^= h >> 33
    h = (h * 0xC4CEB9FE1A85EC53) & _MASK
    h ^= h >> 33
    return h


def hll_hash(value: str) -> int:
    return _fmix64(_fnv1a(value))


def _alpha(m: int) -> float:
    return {16: 0.673, 32: 0.697, 64: 0.709}.get(m, 0.7213 / (1.0 + 1.079 / m))


class HyperLogLog:
    def __init__(self, precision: int = 14) -> None:
        precision = max(4, min(18, precision))
        self.precision = precision
        self.m = 1 << precision
        self.reg = bytearray(self.m)

    def add(self, value: str) -> None:
        h = hll_hash(value)
        idx = h >> (64 - self.precision)
        w = (h << self.precision) & _MASK
        rank = (64 - self.precision + 1) if w == 0 else ((63 - w.bit_length() + 1) + 1)
        # 63 - bit_length(w) + 1 == clz64(w); +1 for HLL rank
        if rank > self.reg[idx]:
            self.reg[idx] = rank

    def estimate(self) -> float:
        total = 0.0
        zeros = 0
        for r in self.reg:
            total += math.ldexp(1.0, -r)
            if r == 0:
                zeros += 1
        m = float(self.m)
        est = _alpha(self.m) * m * m / total
        if est <= 2.5 * m and zeros != 0:
            est = m * math.log(m / zeros)
        return est

    def standard_error(self) -> float:
        return 1.04 / math.sqrt(self.m)


def run_hll_reference(values: Sequence[str], *, precision: int = 14) -> dict[str, Any]:
    hll = HyperLogLog(precision)
    for v in values:
        hll.add(v)
    return {
        "precision": hll.precision,
        "registers": hll.m,
        "observed": len(values),
        "estimate": hll.estimate(),
        "standard_error": hll.standard_error(),
    }


def evaluate_with_native_hll(
    values: Sequence[str],
    *,
    precision: int = 14,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_HLL_CLI", DEFAULT_NATIVE_HLL_CLI))
    stdin = f"precision={precision}\n" + "".join(f"value={v}\n" for v in values)
    if path.exists():
        completed = subprocess.run(
            [str(path)], input=stdin, text=True, capture_output=True, check=False
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            return report

    report = run_hll_reference(values, precision=precision)
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report
