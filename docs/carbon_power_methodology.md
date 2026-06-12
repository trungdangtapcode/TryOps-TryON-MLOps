# Carbon Footprint & Power Cost — Estimation Methodology

This document states exactly how TryOps turns a model run into **energy (Wh)**, **carbon (gCO2e)**, and **money ($)**. Every formula here is implemented in `src/tryops/energy.py` and the native C++ `tryops_energy_stats` engine, and every figure in the benchmark report (`reports/benchmark_run_report.md`) is produced by this method. The goal is that an examiner can audit the numbers, not just trust them.

## 1. What is measured (the only raw input)

We sample **GPU board power** directly from the NVIDIA driver:

- `pynvml.nvmlDeviceGetPowerUsage(handle)` returns instantaneous board power in **milliwatts**; we divide by 1000 → **watts**.
- A background thread (`PowerSampler`) polls this every `interval_s = 0.05 s` (**20 Hz**) for the entire duration of the wrapped inference call, producing a power trace `samples_w` plus the wall-clock `duration_s`.
- If NVML is unavailable (no GPU/driver), a **deterministic fallback trace** is synthesized (idle 20 W endpoints, 70 W active) and the report is marked `"measured": false` — the estimate is never silently faked.

So the two measured quantities are: a **power trace in watts** and a **duration in seconds**. Everything else is derived.

## 2. Energy

Energy is the time-integral of power. With uniform 20 Hz sampling this reduces to mean power × duration:

```
mean_w   = mean(samples_w)                  # average board power over the run (W)
energy_j = mean_w × duration_s              # joules (W·s)
energy_wh  = energy_j / 3600                # watt-hours
energy_kwh = energy_wh / 1000               # kilowatt-hours
```

(Implemented identically in Python `measure_energy` and in native C++ `tryops_energy_stats`; `energy_j = mean_w * duration_s`.)

## 3. Carbon footprint

The standard operational-emissions formula — energy times the grid's carbon intensity (the same approach as CodeCarbon and the Green Software Foundation SCI spec):

```
co2eq_g = energy_kwh × grid_intensity_g_per_kwh
```

- `grid_intensity_g_per_kwh` is a **documented, configurable assumption**, default **475 gCO2e/kWh** (a common world-average for grid electricity). It is recorded in every `tryops.energy.v1` artifact so the assumption travels with the number. Set it to your region's actual grid factor for a local estimate (e.g. ~50 for hydro-heavy grids, ~700 for coal-heavy).

**Software Carbon Intensity (SCI)** — carbon per functional unit (here, per 1,000 tokens):

```
sci_g_per_1k_tokens = co2eq_g / tokens × 1000
```

## 4. Power cost (money)

Two distinct notions of "power cost" — we compute the first and document the second:

**(a) Electricity cost** — what the electricity itself costs:

```
electricity_cost_usd = energy_kwh × electricity_price_usd_per_kwh
electricity_cost_usd_per_1k_tokens = electricity_cost_usd / tokens × 1000
```

- `electricity_price_usd_per_kwh` default **$0.12/kWh** (a common US commercial average), configurable and recorded in the artifact.

**(b) Compute / GPU-rental cost** — what you actually pay a cloud provider, which is billed by *time*, not energy:

```
rental_cost_usd = (gpu_price_usd_per_hour) × (duration_s / 3600)
rental_cost_usd_per_1k_tokens = rental_cost_usd / tokens × 1000
```

This is a documented formula (not auto-filled, since the $/hr depends on your provider/contract). For an NVIDIA L4 a typical on-demand price is ≈ **$0.80/hr**.

> **Key insight (see worked example): rental cost dominates electricity cost by ~100×.** That is *why* throughput (tokens/sec) matters more than raw watts for the dollar bill — and why the slow-but-low-VRAM 8-bit variant is the most expensive option despite drawing fewer watts.

## 5. Other derived efficiency metrics

```
tokens_per_joule       = tokens / energy_j           # higher = greener
energy_delay_product   = energy_j × duration_s        # EDP (J·s), balances energy vs speed
```

## 6. Worked example — from the real benchmark run

Using the **measured** fresh-run figures (`make energy-sample`, `make llm-pareto-sample`, NVIDIA L4, grid 475 gCO2e/kWh, electricity $0.12/kWh, L4 rental $0.80/hr):

| Variant | Wh / 1k tok | gCO2e / 1k tok | tok/s | Electricity $/1M tok | **GPU-rental $/1M tok** |
|---|---|---|---|---|---|
| **fp16** | 0.4067 | 0.193 | 27.4 | $0.0488 | **$8.11** |
| 8-bit | 1.5036 | 0.714 | 5.9 | $0.180 | **$37.66** |
| 4-bit | 0.7319 | 0.348 | 13.9 | $0.0878 | **$15.99** |

Sample derivations for **fp16**:
- Carbon / 1M tokens: `0.4067 Wh/1k × 1000 = 406.7 Wh = 0.4067 kWh` per 1M tokens → `× 475 = 193 gCO2e` per 1M tokens.
- Electricity / 1M tokens: `0.4067 kWh × $0.12 = $0.0488`.
- Rental / 1M tokens: `1,000,000 tokens ÷ 27.4 tok/s = 36,496 s = 10.14 h × $0.80 = $8.11`.

**What this shows:** electricity (~5¢/1M tokens) is ~166× cheaper than GPU rental (~$8/1M tokens), so on cloud the dollar cost tracks **throughput**, not wattage. 8-bit draws the fewest watts yet is the most expensive (slowest), and also the highest-carbon per token — the carbon-aware gate and the SLO gate both reject it for the same root cause (slow decode keeps the GPU busy longer).

## 7. Limitations (state these honestly)

- **Whole-board, not per-process.** NVML reports total GPU power; a co-tenant process would be attributed here. We run benchmarks single-tenant.
- **GPU only.** CPU and RAM energy are not added (CodeCarbon uses Intel RAPL + a RAM estimate for those). For an inference-bound GPU workload the GPU dominates, but the figure is a GPU-energy lower bound on whole-node energy.
- **No datacenter PUE.** Multiply by a Power Usage Effectiveness factor (~1.1–1.5) for facility-level energy.
- **Single static grid factor.** Real grid intensity varies by region and hour; we use one documented constant. Marginal/time-of-use carbon would refine it.
- **Contention sensitivity.** Under concurrent GPU load NVML sampling can fail; the run then degrades to the deterministic fallback trace and is flagged `"measured": false` rather than reported as real.
- **Rental price is an assumption**, not measured — provider- and contract-dependent.

## 8. Reproduce / inspect

```bash
make energy-demo-sample   # smoke-safe: energy+carbon+cost around the deterministic baseline
make energy-sample        # real per-variant GPU energy/carbon/cost sweep
```
Artifacts: `artifacts/eval/energy/*.json` (fields: `energy_wh`, `energy_kwh`, `co2eq_g`, `electricity_cost_usd`, `sci_g_per_1k_tokens`, `electricity_cost_usd_per_1k_tokens`, `tokens_per_joule`, `energy_delay_product_js`).

## 9. References

- CodeCarbon — energy/CO2e via `pynvml` + Intel RAPL: https://github.com/mlco2/codecarbon
- Software Carbon Intensity (SCI) specification — Green Software Foundation: https://sci.greensoftware.foundation/
- NVIDIA Management Library (NVML) power API: https://docs.nvidia.com/deploy/nvml-api/
