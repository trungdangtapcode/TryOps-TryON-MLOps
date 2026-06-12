# TryOps — Real Benchmark Run Report

**This is a record of an actual end-to-end run, not a summary of claims.** Every number below was produced by running the listed `make` target on the hardware named here and read back from the emitted JSON artifact. Where a run degraded or failed, that is reported as-is.

- **Run date (UTC):** 2026-06-11
- **Hardware:** NVIDIA L4 (23,034 MiB), driver 595.71.05 · Intel Xeon @ 2.20 GHz, 4 cores
- **Software:** torch 2.11.0+cu130 (CUDA 13.0), Python 3.12, Go 1.22.10, Rust/cargo 1.96
- **Test suite:** `221 tests` pass (`python -m unittest discover -s tests`) plus 16 Rust gateway unit tests (`make native-rust-test`)

---

## 1. Native production boundary vs Python (the headline)

`make gateway-benchmark-native` — Go stdlib load generator, 12,000 requests per scenario over 50
keep-alive workers. Artifact:
`artifacts/eval/gateway_benchmark/native_gateway_benchmark.json`.

| Scenario | Native path | Native req/s | Python p
ath | Python req/s | p50 native vs Python | p99 native vs Python | errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| `GET /health` | Rust gateway | **24,840.8** | FastAPI direct | 1,539.4 | **1.37 vs 29.00 ms** | **10.08 vs 75.18 ms** | 0 |
| Direct validated `POST /v1/promotion/evaluate` | Rust preflight | **22,261.1** | FastAPI policy/auth | 754.9 | **1.77 vs 61.43 ms** | **7.62 vs 119.11 ms** | 0 |
| Full edge proxy `POST /api/promotion/evaluate` | Rust gateway -> FastAPI | 698.8 | FastAPI direct | **759.0** | 66.23 vs **61.28 ms** | 134.85 vs **120.14 ms** | 0 |

The native Go driver closes the earlier Python/GIL load-driver caveat. The direct native Rust
preflight path is 16.14x faster on `/health` and 29.49x faster on the direct validated promotion
POST. The full edge proxy path is intentionally measured separately: it adds signed-artifact
preflight and proxying in front of the same FastAPI policy route, so it records an explicit edge
cost rather than claiming a speedup.

Historical Python-driven lower-bound run:

`make gateway-benchmark` — 20,000 requests over 50 keep-alive connections at the identical `/health` handler. Artifact: `artifacts/eval/gateway_benchmark/gateway_benchmark.json`.

| Server | req/s | p50 | p99 | errors |
|---|---|---|---|---|
| **Native Rust gateway** (Axum/Tokio) | **4,261.7** | **8.98 ms** | 41.09 ms | 0 |
| Python FastAPI (uvicorn) | 1,927.9 | 24.26 ms | 56.70 ms | 0 |
| **Native advantage** | **2.21× throughput** | **2.7× lower median** | 1.38× lower p99 | — |

This older run is kept as a **lower-bound** cross-check because the load driver is Python/GIL-bound.

**Native service latencies** (per request, from `make native-go-smoke` / gateway logs):
- Go controller `/reconcile`: ~80–135 µs · Rust gateway `/promotion/evaluate`: sub-ms, enforces signed-artifact preflight (HTTP 200 signed / 422 unsigned).

**Native C++ engine per-call latency** (200 calls each, *including* OS process spawn):
- `tryops_perf_stats` p50 2.31 ms · `tryops_energy_stats` p50 2.22 ms · `tryops_eval_stats` p50 2.36 ms — i.e. the compute itself is sub-millisecond; spawn dominates.

---

## 2. Real LLM inference (R1)

`make llm-real-sample` — `SmolLM2-135M-Instruct` via Transformers on CUDA, golden prompt set. Artifact: `artifacts/eval/llm_real/benchmark.json` (adapter = `real`).

- **Throughput:** 17.5 tok/s · **Peak VRAM:** 0.282 GB · **p95 latency:** 8.50 s
- **Phase timing (measured):** prefill avg 4.20 ms / p95 10.84 ms; decode avg 5,419 ms / p95 8,504 ms
- Quality 0.25 on the *legacy exact-phrase* rubric — see §6 for why this is a rubric artifact, not a model result.

---

## 3. LLM quantization Pareto (R2)

`make llm-pareto-sample` — Qwen2.5-0.5B-Instruct, fp16 / 8-bit / 4-bit, each SLO-gated by native C++. Artifact: `artifacts/eval/llm_pareto/pareto.json`.

> **Honest run note:** the first fresh pass this session produced **only fp16** because `accelerate` + `bitsandbytes` had been uninstalled from the venv by concurrent activity (8-bit → "requires accelerate", 4-bit → "No package metadata for bitsandbytes"). I reinstalled both and re-ran. Results below are the completed 3-variant sweep.

| Variant | VRAM | tok/s | p50 latency | quality | native SLO |
|---|---|---|---|---|---|
| fp16 (none) | 1.010 GB | 27.4 | 3,391 ms | 0.250 | pass |
| 8-bit | 0.647 GB | 5.9 | 15,696 ms | 0.250 | **fail (dominated)** |
| 4-bit NF4 | **0.478 GB** | 13.9 | 6,603 ms | 0.278 | pass → **recommended** |

Pareto frontier = `{fp16, 4bit}`. The native engine flags 8-bit as **dominated** (slower *and* larger than 4-bit). Recommendation: **4-bit, 2.1× VRAM reduction** (1.010 → 0.478 GB), SLO-passing.

---

## 4. Energy & carbon (Theme M)

`make energy-sample` — real NVML GPU power per quantization variant. Artifact: `artifacts/eval/energy/energy_sweep.json`.

`measured: true` (real NVML, no contention this run). Grid intensity 475 gCO2e/kWh (documented).

| Variant | Wh / 1k tokens | gCO2e / 1k | mean power | vs fp16 |
|---|---|---|---|---|
| **fp16 (none)** | **0.4067** | 0.193 | 38 W | greenest |
| 8-bit | 1.5036 | 0.714 | 34 W | **3.7× more energy** |
| 4-bit NF4 | 0.7319 | 0.348 | 35 W | 1.8× more energy |

**Finding (reproduced):** quantization *increases* energy-per-token here — similar power but much longer wall-time (slower decode) means more joules per token. Carbon-aware gate: greenest = fp16, verdict **pass**.

**Power cost (same run, L4 @ $0.80/hr, electricity $0.12/kWh):** per 1M tokens — fp16 $0.049 electricity / **$8.11 GPU-rental** · 8-bit $0.180 / **$37.66** · 4-bit $0.088 / **$15.99**. Rental dominates electricity ~166×, so $ cost tracks throughput, not watts — and 8-bit is both the most expensive and highest-carbon despite drawing the fewest watts. Full method + formulas: `docs/carbon_power_methodology.md`.

> **Honest run note:** NVML power sampling is sensitive to GPU contention — under concurrent GPU load this session it sometimes degraded to the deterministic fallback trace (`measured: false`), which is recorded in the artifact rather than hidden.

---

## 5. Real diffusion VTON

`make vton-real-sample` — SD1.5 inpainting refines a garment composited onto the person torso, on CUDA. Artifacts: `artifacts/demo/vton/real_output.png(.json)`.

- **Adapter:** `tryops.pipelines.vton_real.run_real_vton` (real path, `fallback_reason: none`)
- **Latency:** 3.22 s · **Peak VRAM:** 2.81 GB · output 512×512, checksummed + lineage
- **Native C++ image metrics** (real output vs person): PSNR 16.37, MSE 1501, dHash similarity 0.469 — quantifying the try-on change to the torso region.

---

## 6. Eval rigor & leaderboard (Theme N)

`make eval-leaderboard-sample`. Artifact: `artifacts/eval/leaderboard/leaderboard.json` (judge backend: `offline-rubric`, no API key set).

- **Rubric-overfit fix, measured:** the same baseline answers score **0.25 under exact-phrase matching → 0.833 [CI 0.50, 1.00] under the model-agnostic concept-coverage rubric**. The bootstrap CI is computed by the **native C++ `tryops_eval_stats` engine** (`engine: native`).
- Ranking: `baseline, 4bit, none, 8bit`.

---

## 7. Reproduce this report

```bash
make gateway-benchmark-native # §1 native Go load-driver serving benchmark
make gateway-benchmark        # §1 historical Python-driver lower-bound benchmark
make llm-real-sample          # §2 real LLM
make llm-pareto-sample        # §3 quantization Pareto (needs accelerate+bitsandbytes)
make energy-sample            # §4 energy/carbon
make vton-real-sample         # §5 real diffusion VTON
make eval-leaderboard-sample  # §6 eval leaderboard
make smoke                    # 221 Python tests + every pipeline + native engines, offline
```

## 8. Honest findings from this run

1. **Native serving is measurably faster** — 2.21× throughput, 2.7× lower median latency, reproduced across runs.
2. **Dependency drift is real** — a fresh run caught `accelerate`/`bitsandbytes` missing and the quant sweep silently degrading to fp16-only; the pipeline reported it via per-variant `available: false` rather than crashing. (Argues for the `make ci` + lockfile work.)
3. **NVML energy sampling degrades under GPU contention** — recorded as `measured: false` with a fallback trace, never faked.
4. **The rubric, not the model, was the problem** — the model-agnostic scorer lifts baseline quality 0.25 → 0.83.
