#!/usr/bin/env python3
"""Real per-variant GPU energy sweep (Theme M, M005).

Measures the real GPU energy of each LLM quantization variant on the golden
prompt set, computing Wh-per-1k-tokens, CO2e, and Software Carbon Intensity per
variant via the native C++ engine — making energy a first-class axis of the
optimization story alongside the R2 Pareto. Degrades to the deterministic
baseline/fallback when torch/bitsandbytes/GPU are unavailable.
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Real per-variant GPU energy sweep.")
    parser.add_argument("--prompt-set", type=Path, default=Path("samples/eval/golden_prompts.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/energy/energy_sweep.json"))
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--variants", default="none,8bit,4bit")
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--grid-intensity-g-per-kwh", type=float, default=475.0)
    args = parser.parse_args()

    from tryops.pipelines.llm_real import (  # imported lazily so the spine needs no torch
        clear_model_cache,
        generate_once,
        load_model,
        real_model_available,
    )

    prompts = json.loads(args.prompt_set.read_text(encoding="utf-8"))["prompts"]
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    records: list[dict] = []
    real = real_model_available()

    for variant in variants:
        if not real:
            records.append({"variant": variant, "available": False, "error": "torch/transformers unavailable"})
            continue
        try:
            clear_model_cache()
            tokenizer, model, device = load_model(args.model_id, variant, cache=False)
            token_total = {"n": 0}

            def _run_all() -> None:
                for item in prompts:
                    gen = generate_once(tokenizer, model, device, str(item["prompt"]), max_tokens=args.max_tokens)
                    token_total["n"] += int(gen["generated_tokens"])

            _, energy = measure_energy(_run_all, grid_intensity_g_per_kwh=args.grid_intensity_g_per_kwh)
            del model
            clear_model_cache()
            tokens = token_total["n"]
            native = evaluate_with_native_energy_stats(
                energy["samples_w"], energy["duration_s"], tokens=tokens,
                grid_intensity_g_per_kwh=args.grid_intensity_g_per_kwh,
            )
            records.append({
                "variant": variant,
                "available": True,
                "tokens": tokens,
                "measured": energy["measured"],
                "mean_power_w": energy["power_w"]["mean"],
                "peak_power_w": energy["power_w"]["peak"],
                "energy_wh": energy["energy_wh"],
                "co2eq_g": energy["co2eq_g"],
                "energy_wh_per_1k_tokens": native.get("energy_wh_per_1k_tokens"),
                "sci_g_per_1k_tokens": native.get("sci_g_per_1k_tokens"),
                "energy_delay_product_js": native.get("energy_delay_product_js"),
            })
        except Exception as exc:  # degraded mode per variant
            records.append({"variant": variant, "available": False, "error": f"{type(exc).__name__}: {exc}"})

    usable = [r for r in records if r.get("available") and r.get("energy_wh_per_1k_tokens")]
    gate = None
    if len(usable) >= 2:
        baseline = next((r for r in usable if r["variant"] == "none"), usable[0])
        greenest = min(usable, key=lambda r: r["energy_wh_per_1k_tokens"])
        gate = carbon_aware_gate(
            candidate_energy_wh_per_1k=greenest["energy_wh_per_1k_tokens"],
            baseline_energy_wh_per_1k=baseline["energy_wh_per_1k_tokens"],
        )
        gate["greenest_variant"] = greenest["variant"]

    report = {
        "schema_version": "tryops.energy_report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "real-quantization-sweep",
        "model_id": args.model_id,
        "grid_intensity_g_per_kwh": args.grid_intensity_g_per_kwh,
        "variants": records,
        "carbon_gate": gate,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    for r in records:
        if r.get("available"):
            print(f"  {r['variant']:>5}: {r['energy_wh_per_1k_tokens']:.4f} Wh/1k  "
                  f"{r['sci_g_per_1k_tokens']:.4f} gCO2e/1k  mean {r['mean_power_w']:.0f}W  measured={r['measured']}")
        else:
            print(f"  {r['variant']:>5}: unavailable ({r.get('error')})")
    if gate:
        print(f"greenest: {gate['greenest_variant']} -> carbon gate {gate['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
