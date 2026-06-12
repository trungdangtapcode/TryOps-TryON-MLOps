# Green MLOps: Energy and Carbon (Theme M)

TryOps treats energy and carbon as first-class, governed metrics — measured on real hardware, aggregated in compiled code, and enforced at the promotion gate. This is the sustainability dimension of the platform thesis: a model that doubles energy for a marginal quality gain should not ship.

## What is measured

Each real inference is wrapped by a background **power sampler** (`src/tryops/energy.py`) that polls NVIDIA NVML (`pynvml`) GPU power (watts) at a fixed interval and integrates it over wall-clock time. When no GPU/NVML is present it synthesizes a deterministic power trace, so the pipeline, the native engine, the carbon gate, and `make smoke` all run offline — the same simulation-first discipline as the rest of the platform.

The `tryops.energy.v1` artifact records: measured power trace (mean/peak/min W), `energy_j`, `energy_wh`, `co2eq_g`, `tokens_per_joule`, `energy_delay_product`, and Software Carbon Intensity (`sci_g_per_1k_tokens`).

## Native aggregation (compiled hot path)

The heavy aggregation runs in **native C++** `tryops_energy_stats` (`native/cpp/tryops_energy_stats/`), bridged by `src/tryops/native_energy_stats.py` — the same Python-marshals / C++-computes split as `tryops_perf_stats`. Given a power trace + duration + token count + grid intensity it emits energy, CO2e, SCI, EDP, and a **carbon-aware gate verdict**.

## Carbon factor assumption

> Full estimation methodology, formulas, worked examples, and limitations: [`docs/carbon_power_methodology.md`](carbon_power_methodology.md).


CO2e is `energy_kWh × grid_intensity`. The grid intensity is a documented, configurable value defaulting to **475 gCO2e/kWh** (a common world-average). Record the value used alongside every result; it is the single assumption behind the carbon figures.

## Carbon-aware promotion gate

`carbon_aware_gate()` (and the native engine's gate) reject a candidate whose **energy-per-1k-tokens** exceeds an absolute ceiling or regresses beyond a percentage versus the current champion — making sustainability a promotion criterion, not just a dashboard number.

## Reproduce

```bash
make energy-demo-sample   # smoke-safe: energy around the deterministic baseline (real NVML if present)
make energy-sample        # GPU: real per-variant energy of the fp16/8-bit/4-bit quantization sweep
```

`energy-sample` makes energy a first-class axis of the optimization story alongside the R2 Pareto: Wh-per-1k-tokens and gCO2e-per-1k-tokens per quantization variant.

## Grafana visibility

`infra/grafana/dashboards/tryops-cost-capacity.json` includes Energy per 1k Tokens, CO2e per 1k Tokens, and Cost vs Energy Correlation panels. The local evidence source is `artifacts/eval/energy/energy_sweep.json`; production exporters should expose `tryops_energy_wh_per_1k_tokens`, `tryops_co2e_g_per_1k_tokens`, and `tryops_request_cost_usd_per_1k_tokens`.

## Metrics glossary

- **energy_wh** — watt-hours consumed by the run (mean power × duration).
- **SCI (gCO2e per 1k tokens)** — Software Carbon Intensity per functional unit (Green Software Foundation).
- **tokens_per_joule** — throughput-per-energy; higher is greener.
- **EDP (energy-delay product)** — `energy × latency`; balances efficiency against speed.

## References

- CodeCarbon — energy/CO2e tracking via pynvml + Intel RAPL: https://github.com/mlco2/codecarbon
- Software Carbon Intensity specification (Green Software Foundation): https://sci.greensoftware.foundation/
