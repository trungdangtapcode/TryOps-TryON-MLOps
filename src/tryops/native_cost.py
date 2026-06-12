"""Bridge to the native C++ cost-attribution (FinOps showback) engine.

The Python reference mirrors the engine's cost arithmetic exactly so per-tenant /
per-model / total chargeback numbers agree bit-for-bit with the native binary.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_COST_CLI = Path("artifacts/native/tryops_cost_cli")


@dataclass
class PricingConfig:
    gpu_usd_per_hr: float = 2.50
    electricity_usd_per_kwh: float = 0.12
    grid_g_per_kwh: float = 475.0
    default_in_per_1k: float = 0.0
    default_out_per_1k: float = 0.0
    model_prices: dict[str, tuple[float, float]] = field(default_factory=dict)

    def price_for(self, model: str) -> tuple[float, float]:
        return self.model_prices.get(model, (self.default_in_per_1k, self.default_out_per_1k))


@dataclass
class UsageEvent:
    tenant: str
    model: str
    in_tokens: int = 0
    out_tokens: int = 0
    gpu_seconds: float = 0.0
    energy_wh: float = 0.0


def _empty_bucket() -> dict[str, Any]:
    return {
        "requests": 0, "in_tokens": 0, "out_tokens": 0,
        "token_usd": 0.0, "gpu_usd": 0.0, "energy_usd": 0.0,
        "total_usd": 0.0, "carbon_g": 0.0,
    }


def _add(bucket: dict[str, Any], ev: UsageEvent, cfg: PricingConfig) -> None:
    in_p, out_p = cfg.price_for(ev.model)
    token_usd = (ev.in_tokens / 1000.0) * in_p + (ev.out_tokens / 1000.0) * out_p
    gpu_usd = (ev.gpu_seconds / 3600.0) * cfg.gpu_usd_per_hr
    kwh = ev.energy_wh / 1000.0
    energy_usd = kwh * cfg.electricity_usd_per_kwh
    carbon = kwh * cfg.grid_g_per_kwh
    bucket["requests"] += 1
    bucket["in_tokens"] += ev.in_tokens
    bucket["out_tokens"] += ev.out_tokens
    bucket["token_usd"] += token_usd
    bucket["gpu_usd"] += gpu_usd
    bucket["energy_usd"] += energy_usd
    bucket["total_usd"] += token_usd + gpu_usd + energy_usd
    bucket["carbon_g"] += carbon


def run_cost_reference(
    events: Sequence[UsageEvent], cfg: PricingConfig
) -> dict[str, Any]:
    per_tenant: dict[str, dict[str, Any]] = {}
    per_model: dict[str, dict[str, Any]] = {}
    total = _empty_bucket()
    for ev in events:
        _add(per_tenant.setdefault(ev.tenant, _empty_bucket()), ev, cfg)
        _add(per_model.setdefault(ev.model, _empty_bucket()), ev, cfg)
        _add(total, ev, cfg)
    return {"per_tenant": per_tenant, "per_model": per_model, "total": total}


def _serialize(events: Sequence[UsageEvent], cfg: PricingConfig) -> str:
    lines = [
        f"gpu_usd_per_hr={cfg.gpu_usd_per_hr}",
        f"electricity_usd_per_kwh={cfg.electricity_usd_per_kwh}",
        f"grid_g_per_kwh={cfg.grid_g_per_kwh}",
        f"default_in_per_1k={cfg.default_in_per_1k}",
        f"default_out_per_1k={cfg.default_out_per_1k}",
    ]
    for model, (in_p, out_p) in sorted(cfg.model_prices.items()):
        lines.append(f"price.{model}.in_per_1k={in_p}")
        lines.append(f"price.{model}.out_per_1k={out_p}")
    for ev in events:
        lines.append(
            f"event=tenant={ev.tenant};model={ev.model};in={ev.in_tokens};"
            f"out={ev.out_tokens};gpu_s={ev.gpu_seconds};wh={ev.energy_wh}"
        )
    return "\n".join(lines) + "\n"


def evaluate_with_native_cost(
    events: Sequence[UsageEvent],
    cfg: PricingConfig,
    *,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_COST_CLI", DEFAULT_NATIVE_COST_CLI))
    if path.exists():
        completed = subprocess.run(
            [str(path)], input=_serialize(events, cfg),
            text=True, capture_output=True, check=False,
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            return report

    report = run_cost_reference(events, cfg)
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report
