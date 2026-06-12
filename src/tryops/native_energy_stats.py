"""Bridge to the native C++ energy / carbon aggregation engine.

Energy, CO2e, Software Carbon Intensity, and the carbon-aware promotion verdict
are computed in compiled ``tryops_energy_stats`` rather than Python, keeping the
Green-MLOps hot path on the production-language boundary. Degrades gracefully
(``available=False``) when the binary is absent so the spine never requires the
native toolchain.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_ENERGY_STATS_CLI = Path("artifacts/native/tryops_energy_stats_cli")


def _format_samples(values: Sequence[float]) -> str:
    return ",".join(repr(float(v)) for v in values)


def evaluate_with_native_energy_stats(
    samples_w: Sequence[float],
    duration_s: float,
    *,
    tokens: int = 0,
    grid_intensity_g_per_kwh: float = 475.0,
    energy_wh_per_1k_tokens_max: float | None = None,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    """Aggregate a power trace into energy/carbon stats + carbon-aware verdict."""

    if not samples_w:
        raise ValueError("samples_w cannot be empty")
    if duration_s <= 0:
        raise ValueError("duration_s must be > 0")

    path = Path(
        cli_path
        or os.environ.get("TRYOPS_NATIVE_ENERGY_STATS_CLI", DEFAULT_NATIVE_ENERGY_STATS_CLI)
    )
    if not path.exists():
        return {
            "available": False,
            "cli_path": str(path),
            "reason": "native energy stats CLI not found",
        }

    lines = [
        f"samples.power_w={_format_samples(samples_w)}",
        f"duration_s={float(duration_s)}",
        f"tokens={int(tokens)}",
        f"grid_intensity_g_per_kwh={float(grid_intensity_g_per_kwh)}",
    ]
    if energy_wh_per_1k_tokens_max is not None:
        lines.append(f"slo.energy_wh_per_1k_tokens_max={float(energy_wh_per_1k_tokens_max)}")
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
