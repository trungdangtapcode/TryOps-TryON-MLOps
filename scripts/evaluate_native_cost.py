#!/usr/bin/env python3
"""Attribute cost + carbon per tenant/model from a usage stream using the native
engine, cross-check totals against the Python reference, and write a showback
report.
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

from tryops.native_cost import (  # noqa: E402
    PricingConfig,
    UsageEvent,
    evaluate_with_native_cost,
    run_cost_reference,
)


def load_events(path: Path) -> tuple[PricingConfig, list[UsageEvent]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pc = data.get("pricing", {})
    cfg = PricingConfig(
        gpu_usd_per_hr=pc.get("gpu_usd_per_hr", 2.50),
        electricity_usd_per_kwh=pc.get("electricity_usd_per_kwh", 0.12),
        grid_g_per_kwh=pc.get("grid_g_per_kwh", 475.0),
        default_in_per_1k=pc.get("default_in_per_1k", 0.0),
        default_out_per_1k=pc.get("default_out_per_1k", 0.0),
        model_prices={m: (p["in_per_1k"], p["out_per_1k"]) for m, p in pc.get("models", {}).items()},
    )
    events = [
        UsageEvent(
            tenant=e["tenant"], model=e["model"],
            in_tokens=e.get("in", 0), out_tokens=e.get("out", 0),
            gpu_seconds=e.get("gpu_s", 0.0), energy_wh=e.get("wh", 0.0),
        )
        for e in data.get("events", [])
    ]
    return cfg, events


def main() -> int:
    parser = argparse.ArgumentParser(description="Native FinOps cost attribution.")
    parser.add_argument("--input", type=Path, default=Path("samples/cost/usage.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/cost/cost_report.json"))
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    cfg, events = load_events(args.input)
    report = evaluate_with_native_cost(events, cfg, cli_path=args.cli)
    reference = run_cost_reference(events, cfg)

    def close(a, b):
        return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(b)))

    total_keys = ("token_usd", "gpu_usd", "energy_usd", "total_usd", "carbon_g")
    agrees = all(close(report["total"][k], reference["total"][k]) for k in total_keys)

    out = {
        "schema_version": "tryops.native_cost.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "input": str(args.input),
        "engine": report.get("engine"),
        "per_tenant": report.get("per_tenant"),
        "per_model": report.get("per_model"),
        "total": report.get("total"),
        "reference_totals_agree": agrees,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    t = report["total"]
    print(
        f"[cost] engine={report.get('engine')} requests={t['requests']} "
        f"token=${t['token_usd']:.4f} gpu=${t['gpu_usd']:.4f} "
        f"energy=${t['energy_usd']:.4f} total=${t['total_usd']:.4f} "
        f"carbon={t['carbon_g']:.1f}g tenants={len(report.get('per_tenant', {}))} "
        f"reference_agrees={agrees}"
    )
    print(f"[cost] wrote {args.output}")
    return 0 if agrees else 2


if __name__ == "__main__":
    raise SystemExit(main())
