"""Bridge to the native C++ benchmark statistics / SLO engine.

The percentile + throughput + SLO-gate computation runs in compiled C++
(``tryops_perf_stats``) rather than Python, keeping the performance hot path on
the production-language boundary. Python only marshals samples in and JSON out,
and degrades gracefully (``available=False``) when the binary is absent so the
deterministic spine never requires the native toolchain.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_PERF_STATS_CLI = Path("artifacts/native/tryops_perf_stats_cli")


def _format_samples(values: Sequence[float]) -> str:
    return ",".join(repr(float(v)) for v in values)


def evaluate_with_native_perf_stats(
    latency_ms: Sequence[float],
    tokens_per_second: Sequence[float] | None = None,
    *,
    latency_p95_ms_max: float | None = None,
    tokens_per_second_min: float | None = None,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compute latency percentiles, throughput, and an SLO verdict in native C++."""

    if not latency_ms:
        raise ValueError("latency_ms cannot be empty")

    path = Path(
        cli_path
        or os.environ.get("TRYOPS_NATIVE_PERF_STATS_CLI", DEFAULT_NATIVE_PERF_STATS_CLI)
    )
    if not path.exists():
        return {
            "available": False,
            "cli_path": str(path),
            "reason": "native perf stats CLI not found",
        }

    lines = [f"samples.latency_ms={_format_samples(latency_ms)}"]
    if tokens_per_second:
        lines.append(f"samples.tokens_per_second={_format_samples(tokens_per_second)}")
    if latency_p95_ms_max is not None:
        lines.append(f"slo.latency_p95_ms_max={float(latency_p95_ms_max)}")
    if tokens_per_second_min is not None:
        lines.append(f"slo.tokens_per_second_min={float(tokens_per_second_min)}")
    payload = "\n".join(lines) + "\n"

    completed = subprocess.run(
        [str(path)],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return {
            "available": True,
            "cli_path": str(path),
            "returncode": completed.returncode,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    stats = json.loads(completed.stdout)
    stats["available"] = True
    stats["cli_path"] = str(path)
    stats["returncode"] = completed.returncode
    return stats
