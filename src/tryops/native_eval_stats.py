"""Bridge to the native C++ bootstrap-CI engine (Theme N).

The resampling-heavy bootstrap confidence interval runs in compiled
``tryops_eval_stats`` rather than Python, keeping the statistical hot path on the
production-language boundary. ``bootstrap_ci_preferred`` uses the native engine
when the binary is present and falls back to the pure-Python implementation
otherwise, so the eval pipeline stays runnable without the toolchain.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence

from tryops.evaluation import bootstrap_ci as _python_bootstrap_ci

DEFAULT_NATIVE_EVAL_STATS_CLI = Path("artifacts/native/tryops_eval_stats_cli")


def bootstrap_ci_native(
    values: Sequence[float],
    *,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
    cli_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return a native bootstrap CI, or None if the binary is unavailable/fails."""

    if not values:
        raise ValueError("values cannot be empty")
    path = Path(
        cli_path or os.environ.get("TRYOPS_NATIVE_EVAL_STATS_CLI", DEFAULT_NATIVE_EVAL_STATS_CLI)
    )
    if not path.exists():
        return None
    payload = (
        f"samples.values={','.join(repr(float(v)) for v in values)}\n"
        f"n_resamples={int(n_resamples)}\nconfidence={float(confidence)}\nseed={int(seed)}\n"
    )
    completed = subprocess.run(
        [str(path)], input=payload, text=True, capture_output=True, check=False, timeout=10
    )
    if completed.returncode != 0:
        return None
    stats = json.loads(completed.stdout)
    stats["engine"] = "native"
    return stats


def bootstrap_ci_preferred(
    values: Sequence[float],
    *,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    """Native bootstrap CI when available, else the pure-Python implementation."""

    native = bootstrap_ci_native(
        values, n_resamples=n_resamples, confidence=confidence, seed=seed
    )
    if native is not None:
        return native
    result = _python_bootstrap_ci(
        values, n_resamples=n_resamples, confidence=confidence, seed=seed
    )
    result["engine"] = "python-fallback"
    return result
