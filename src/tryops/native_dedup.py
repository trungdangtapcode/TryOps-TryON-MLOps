"""Bridge to the native C++ Bloom-filter idempotency dedup engine.

The Python reference reproduces the exact FNV-1a double-hashing and optimal
sizing math of the C++ engine so the two agree bit-for-bit on which keys are
admitted vs. rejected as duplicates.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_DEDUP_CLI = Path("artifacts/native/tryops_dedup_cli")

_MASK = (1 << 64) - 1
_FNV_OFFSET = 1469598103934665603
_FNV_PRIME = 1099511628211
_LN2 = 0.6931471805599453


def _fnv1a(data: str, basis: int) -> int:
    h = basis
    for b in data.encode("utf-8", "surrogatepass"):
        h ^= b
        h = (h * _FNV_PRIME) & _MASK
    return h


def optimal_bits(n: int, p: float) -> int:
    n = max(1, n)
    if not (0.0 < p < 1.0):
        p = 0.01
    m = -(n * math.log(p)) / (_LN2 * _LN2)
    bits = math.ceil(m)
    return max(64, bits)


def optimal_hashes(m: int, n: int) -> int:
    n = max(1, n)
    k = (m / n) * _LN2
    hashes = math.floor(k + 0.5)  # round-half-up, matches C++ std::round for k>0
    return min(32, max(1, hashes))


class BloomFilter:
    def __init__(self, expected_items: int, target_fp_rate: float) -> None:
        self.bits = optimal_bits(expected_items, target_fp_rate)
        self.hashes = optimal_hashes(self.bits, expected_items)
        self.words = bytearray(((self.bits + 63) // 64) * 8)
        self._w = memoryview(self.words).cast("Q")  # 64-bit words

    def _positions(self, key: str) -> list[int]:
        h1 = _fnv1a(key, _FNV_OFFSET)
        h2 = _fnv1a(key, _FNV_PRIME) | 1
        out = []
        combined = h1
        for _ in range(self.hashes):
            out.append(combined % self.bits)
            combined = (combined + h2) & _MASK
        return out

    def insert_if_absent(self, key: str) -> bool:
        present = True
        for p in self._positions(key):
            wi, bit = divmod(p, 64)
            mask = 1 << bit
            if not (self._w[wi] & mask):
                present = False
                self._w[wi] |= mask
        return not present

    def maybe_contains(self, key: str) -> bool:
        for p in self._positions(key):
            wi, bit = divmod(p, 64)
            if not (self._w[wi] & (1 << bit)):
                return False
        return True

    def set_bits(self) -> int:
        return sum(bin(self._w[i]).count("1") for i in range(len(self._w)))


def run_dedup_reference(
    keys: Sequence[str], *, expected_items: int, target_fp_rate: float
) -> dict[str, Any]:
    f = BloomFilter(expected_items, target_fp_rate)
    total = admitted = 0
    for k in keys:
        total += 1
        if f.insert_if_absent(k):
            admitted += 1
    set_bits = f.set_bits()
    fill = set_bits / f.bits if f.bits else 0.0
    return {
        "total": total,
        "admitted": admitted,
        "rejected_dupe": total - admitted,
        "bits": f.bits,
        "hashes": f.hashes,
        "set_bits": set_bits,
        "fill_ratio": fill,
        "theoretical_fp_rate": fill ** f.hashes,
    }


def evaluate_with_native_dedup(
    keys: Sequence[str],
    *,
    expected_items: int = 10000,
    target_fp_rate: float = 0.01,
    max_fp_rate: float = 1.0,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(
        cli_path or os.environ.get("TRYOPS_NATIVE_DEDUP_CLI", DEFAULT_NATIVE_DEDUP_CLI)
    )
    header = f"expected_items={expected_items}\ntarget_fp_rate={target_fp_rate}\n"
    stdin = header + "".join(f"key={k}\n" for k in keys)
    if path.exists():
        completed = subprocess.run(
            [str(path), "--max-fp-rate", str(max_fp_rate)],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            return report

    report = run_dedup_reference(
        keys, expected_items=expected_items, target_fp_rate=target_fp_rate
    )
    report["gate_ok"] = report["theoretical_fp_rate"] <= max_fp_rate
    report["max_fp_rate"] = max_fp_rate
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report
