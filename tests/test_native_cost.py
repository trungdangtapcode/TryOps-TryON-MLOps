"""Tests for the native cost-attribution bridge + native/reference parity."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

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

CLI = ROOT / "artifacts" / "native" / "tryops_cost_cli"


def test_cost_math():
    cfg = PricingConfig(
        gpu_usd_per_hr=3.60, electricity_usd_per_kwh=0.10, grid_g_per_kwh=400.0,
        model_prices={"qwen": (0.05, 0.15)},
    )
    ev = UsageEvent("acme", "qwen", in_tokens=1000, out_tokens=2000, gpu_seconds=3600, energy_wh=1000)
    r = run_cost_reference([ev], cfg)
    t = r["total"]
    assert t["token_usd"] == pytest.approx(0.35)
    assert t["gpu_usd"] == pytest.approx(3.60)
    assert t["energy_usd"] == pytest.approx(0.10)
    assert t["carbon_g"] == pytest.approx(400.0)


def test_tenant_attribution():
    cfg = PricingConfig(model_prices={"m": (0.10, 0.10)})
    events = [
        UsageEvent("a", "m", in_tokens=1000),
        UsageEvent("b", "m", in_tokens=2000),
    ]
    r = run_cost_reference(events, cfg)
    assert r["per_tenant"]["a"]["token_usd"] == pytest.approx(0.10)
    assert r["per_tenant"]["b"]["token_usd"] == pytest.approx(0.20)
    assert r["total"]["token_usd"] == pytest.approx(0.30)
    assert r["per_model"]["m"]["token_usd"] == pytest.approx(0.30)


def test_default_pricing_fallback():
    cfg = PricingConfig(default_in_per_1k=0.02, default_out_per_1k=0.02)
    r = run_cost_reference([UsageEvent("x", "unknown", in_tokens=1000, out_tokens=1000)], cfg)
    assert r["total"]["token_usd"] == pytest.approx(0.04)


@pytest.mark.skipif(not CLI.exists(), reason="native cost CLI not built")
def test_native_matches_reference():
    cfg = PricingConfig(
        gpu_usd_per_hr=2.50,
        model_prices={"qwen": (0.05, 0.15), "smol": (0.02, 0.06)},
    )
    events = [
        UsageEvent(f"t{i % 4}", "qwen" if i % 2 else "smol",
                   in_tokens=100 + i, out_tokens=50 + i,
                   gpu_seconds=0.5 + i * 0.01, energy_wh=0.02 + i * 0.001)
        for i in range(500)
    ]
    native = evaluate_with_native_cost(events, cfg, cli_path=CLI)
    reference = run_cost_reference(events, cfg)
    assert native["engine"] == "native"
    for key in ("token_usd", "gpu_usd", "energy_usd", "total_usd", "carbon_g"):
        assert native["total"][key] == pytest.approx(reference["total"][key], rel=1e-6, abs=1e-9)
    # per-tenant attribution reconciles
    for tenant, bucket in reference["per_tenant"].items():
        assert native["per_tenant"][tenant]["total_usd"] == pytest.approx(
            bucket["total_usd"], rel=1e-6, abs=1e-9
        )
