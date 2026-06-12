"""GPU energy / carbon sampling for the Green-MLOps tranche (Theme M).

Wraps a callable with a background power sampler (``pynvml`` / NVML) and emits a
``tryops.energy.v1`` report: real measured GPU power trace, energy (Wh), CO2e,
and the functional-unit intensities. Mirrors the platform discipline — real GPU
telemetry behind a deterministic fallback so the contract and ``make smoke``
never require a GPU. The heavy aggregation (mean/peak W, kWh, SCI, carbon gate)
runs in the native C++ ``tryops_energy_stats`` engine; this module marshals.
"""

from __future__ import annotations

import threading
from time import perf_counter, sleep
from typing import Any, Callable

# World-average grid carbon intensity (gCO2e/kWh). Documented, configurable
# assumption — see configs and the data/model card. ~475 is a common default.
DEFAULT_GRID_INTENSITY_G_PER_KWH = 475.0

# Electricity price (USD/kWh) for the power-cost estimate. Documented, configurable
# assumption — ~0.12 is a common US commercial average. See docs/carbon_power_methodology.md.
DEFAULT_ELECTRICITY_PRICE_USD_PER_KWH = 0.12

# Fallback power model when NVML is unavailable: a deterministic constant draw so
# the energy pipeline, native engine, and carbon gate stay runnable offline.
FALLBACK_IDLE_W = 20.0
FALLBACK_ACTIVE_W = 70.0


def nvml_available() -> bool:
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import pynvml

        pynvml.nvmlInit()
        pynvml.nvmlShutdown()
        return True
    except Exception:
        return False


class PowerSampler:
    """Background thread that polls GPU power (watts) at a fixed interval."""

    def __init__(self, *, device_index: int = 0, interval_s: float = 0.05) -> None:
        self.device_index = device_index
        self.interval_s = interval_s
        self.samples_w: list[float] = []
        self.device_name: str | None = None
        self.measured = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "PowerSampler":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def start(self) -> None:
        if not nvml_available():
            return  # measured stays False; caller synthesizes a fallback trace
        self.measured = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        # Any NVML hiccup (bad index, transient driver error, concurrent reader)
        # must not escape the daemon thread — degrade to whatever was collected.
        try:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                import pynvml

            pynvml.nvmlInit()
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(self.device_index)
                name = pynvml.nvmlDeviceGetName(handle)
                self.device_name = name.decode() if isinstance(name, bytes) else str(name)
                while not self._stop.is_set():
                    self.samples_w.append(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0)
                    sleep(self.interval_s)
                # one final reading so very short runs still get a sample
                self.samples_w.append(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0)
            finally:
                pynvml.nvmlShutdown()
        except Exception:
            return

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def _fallback_trace(duration_s: float, interval_s: float) -> list[float]:
    n = max(2, int(duration_s / max(interval_s, 1e-6)))
    # Deterministic active draw — represents work between idle endpoints.
    return [FALLBACK_IDLE_W] + [FALLBACK_ACTIVE_W] * (n - 2) + [FALLBACK_IDLE_W]


def measure_energy(
    fn: Callable[[], Any],
    *,
    tokens: int = 0,
    grid_intensity_g_per_kwh: float = DEFAULT_GRID_INTENSITY_G_PER_KWH,
    electricity_price_usd_per_kwh: float = DEFAULT_ELECTRICITY_PRICE_USD_PER_KWH,
    device_index: int = 0,
    interval_s: float = 0.05,
) -> tuple[Any, dict[str, Any]]:
    """Run ``fn`` while sampling GPU power; return ``(result, energy_report)``.

    The report follows ``tryops.energy.v1`` and is the same shape whether the
    power trace is measured (NVML) or synthesized (fallback), so downstream
    aggregation and dashboards are identical.
    """

    sampler = PowerSampler(device_index=device_index, interval_s=interval_s)
    started = perf_counter()
    sampler.start()
    try:
        result = fn()
    finally:
        sampler.stop()
    duration_s = max(perf_counter() - started, 1e-6)

    used_measured = bool(sampler.measured and sampler.samples_w)
    if used_measured:
        samples_w = sampler.samples_w
        source = "nvml"
        device_name = sampler.device_name
    else:
        samples_w = _fallback_trace(duration_s, interval_s)
        source = "deterministic-fallback"
        device_name = None

    mean_w = sum(samples_w) / len(samples_w)
    energy_j = mean_w * duration_s
    energy_j_report = round(energy_j, 6)
    energy_wh = energy_j_report / 3600.0
    energy_kwh = energy_wh / 1000.0
    co2eq_g = energy_kwh * grid_intensity_g_per_kwh
    electricity_cost_usd = energy_kwh * electricity_price_usd_per_kwh

    report: dict[str, Any] = {
        "schema_version": "tryops.energy.v1",
        "measured": used_measured,
        "source": source,
        "device_name": device_name,
        "duration_s": round(duration_s, 6),
        "tokens": int(tokens),
        "grid_intensity_g_per_kwh": grid_intensity_g_per_kwh,
        "electricity_price_usd_per_kwh": electricity_price_usd_per_kwh,
        "power_w": {
            "mean": round(mean_w, 6),
            "peak": round(max(samples_w), 6),
            "min": round(min(samples_w), 6),
            "samples": len(samples_w),
        },
        "energy_j": energy_j_report,
        "energy_wh": round(energy_wh, 12),
        "energy_kwh": round(energy_kwh, 15),
        "co2eq_g": round(co2eq_g, 12),
        "electricity_cost_usd": round(electricity_cost_usd, 12),
        "samples_w": [round(w, 4) for w in samples_w],
    }
    if tokens > 0:
        report["energy_wh_per_1k_tokens"] = round(energy_wh / tokens * 1000.0, 9)
        report["sci_g_per_1k_tokens"] = round(co2eq_g / tokens * 1000.0, 9)
        report["tokens_per_joule"] = round(tokens / energy_j, 9) if energy_j > 0 else 0.0
        report["electricity_cost_usd_per_1k_tokens"] = round(
            electricity_cost_usd / tokens * 1000.0, 12
        )
    return result, report


def carbon_aware_gate(
    *,
    candidate_energy_wh_per_1k: float,
    baseline_energy_wh_per_1k: float | None = None,
    max_energy_wh_per_1k: float | None = None,
    max_regression_pct: float = 20.0,
) -> dict[str, Any]:
    """Decide promotion on sustainability grounds (Theme M, M006).

    Rejects a candidate whose energy-per-1k-tokens exceeds an absolute ceiling or
    regresses beyond ``max_regression_pct`` versus the current champion. Returns a
    governance-shaped verdict consumable by the promotion pipeline.
    """

    reasons: list[str] = []
    passed = True

    if max_energy_wh_per_1k is not None and candidate_energy_wh_per_1k > max_energy_wh_per_1k:
        passed = False
        reasons.append(
            f"energy {candidate_energy_wh_per_1k:.4f} Wh/1k exceeds ceiling "
            f"{max_energy_wh_per_1k:.4f}"
        )

    regression_pct = None
    if baseline_energy_wh_per_1k is not None and baseline_energy_wh_per_1k > 0:
        regression_pct = (
            (candidate_energy_wh_per_1k - baseline_energy_wh_per_1k)
            / baseline_energy_wh_per_1k
            * 100.0
        )
        if regression_pct > max_regression_pct:
            passed = False
            reasons.append(
                f"energy regressed {regression_pct:.1f}% vs champion "
                f"(limit {max_regression_pct:.1f}%)"
            )

    if passed:
        reasons.append("carbon-aware gate passed")

    return {
        "schema_version": "tryops.carbon_gate.v1",
        "candidate_energy_wh_per_1k_tokens": round(candidate_energy_wh_per_1k, 9),
        "baseline_energy_wh_per_1k_tokens": (
            round(baseline_energy_wh_per_1k, 9) if baseline_energy_wh_per_1k is not None else None
        ),
        "regression_pct": round(regression_pct, 4) if regression_pct is not None else None,
        "max_energy_wh_per_1k_tokens": max_energy_wh_per_1k,
        "max_regression_pct": max_regression_pct,
        "passed": passed,
        "verdict": "pass" if passed else "fail",
        "reasons": reasons,
    }
