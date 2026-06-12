#!/usr/bin/env python3
"""Green-MLOps energy demo (Theme M) — smoke-safe.

Measures GPU energy around the deterministic LLM baseline (real NVML power when a
GPU is present, deterministic fallback otherwise), aggregates with the native C++
energy engine, and runs the carbon-aware promotion gate. Fast and offline so it
belongs in ``make smoke``.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.energy import carbon_aware_gate, measure_energy  # noqa: E402
from tryops.native_energy_stats import evaluate_with_native_energy_stats  # noqa: E402
from tryops.pipelines.llm_baseline import (  # noqa: E402
    estimate_tokens,
    generate_baseline_response,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Green-MLOps energy demo (smoke-safe).")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/energy/energy_demo.json"))
    parser.add_argument("--grid-intensity-g-per-kwh", type=float, default=475.0)
    parser.add_argument("--energy-wh-per-1k-max", type=float, default=50.0)
    parser.add_argument("--prompt", default="Summarize why MLOps governs VTON and LLM models.")
    args = parser.parse_args()

    holder: dict[str, object] = {}

    def _run() -> None:
        holder["gen"] = generate_baseline_response(prompt=args.prompt, max_tokens=128)

    _, energy = measure_energy(_run, grid_intensity_g_per_kwh=args.grid_intensity_g_per_kwh)
    gen = holder["gen"]
    tokens = int(estimate_tokens(gen["output"]["text"]))  # type: ignore[index]

    native = evaluate_with_native_energy_stats(
        energy["samples_w"],
        energy["duration_s"],
        tokens=tokens,
        grid_intensity_g_per_kwh=args.grid_intensity_g_per_kwh,
        energy_wh_per_1k_tokens_max=args.energy_wh_per_1k_max,
    )
    candidate_wh_per_1k = native.get("energy_wh_per_1k_tokens", 0.0) if native.get("available") else 0.0
    gate = carbon_aware_gate(
        candidate_energy_wh_per_1k=candidate_wh_per_1k,
        max_energy_wh_per_1k=args.energy_wh_per_1k_max,
    )

    report = {
        "schema_version": "tryops.energy_report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "demo-deterministic-baseline",
        "tokens": tokens,
        "energy": energy,
        "native_energy_stats": native,
        "carbon_gate": gate,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"source={energy['source']} measured={energy['measured']} "
        f"mean_W={energy['power_w']['mean']:.1f} energy_Wh={energy['energy_wh']:.6f} "
        f"co2e_g={energy['co2eq_g']:.6f} gate={gate['verdict']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
