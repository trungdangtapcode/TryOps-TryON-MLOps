# Defense Q&A — Tough Questions, Concise Answers

Anticipated examiner questions with evidence-backed answers. Each answer points to a runnable command or artifact.

## Thesis & scope

**Q: This looks like a lot of plumbing. Where is the research?**
The research question is *how to make ML production-grade*, measured by MLOps maturity. The empirical contributions are concrete: a measured quantization Pareto frontier, a demonstration that SLO thresholds don't transfer between adapters, and a counter-intuitive energy finding (quantization costs energy here). Evidence: `make llm-pareto-sample`, `make energy-sample`.

**Q: Isn't most of this simulated?**
Yes, deliberately — and that is a feature, not a hidden gap. A deterministic spine establishes every contract, gate, and dashboard so the whole system is reproducible on any machine; real GPU backends slot in behind the *same* contracts. The honest, file-by-file split is in `docs/roadmap_audit.md` and the roadmap Reality Ledger, using a three-state legend (`[x]` real, `[~]` contract-only, `[ ]` not started). The platform audits its own claims.

## Optimization

**Q: You claim 4-bit is best — prove it.**
On Qwen2.5-0.5B on an L4: 4-bit NF4 gives 2.1× VRAM reduction (1.01→0.48 GB) at 11.3 tok/s and passes the native SLO; 8-bit is *dominated* — slower (4.5 tok/s) and larger (0.65 GB) than 4-bit — so the recommender rejects it. Artifact: `artifacts/eval/llm_pareto/pareto.json`.

**Q: Quantization is supposed to be faster. Why is 8-bit slow?**
bitsandbytes 8-bit has high per-token dequantization overhead that dominates on a small model, so wall-time rises. This is exactly why the platform *measures* rather than assumes — and why the energy finding below matters.

**Q: Why did real models score only 0.25 quality?**
That is a real evaluation bug we surface honestly: the golden rubric was tuned to the deterministic baseline's exact wording, so fluent real-model answers fail string-level criteria. The fix is designed as Wave 2 Theme N (model-agnostic semantic scoring + a Claude LLM-as-judge with bootstrap confidence intervals). It is a rubric problem, not a model regression.

## Sustainability

**Q: Why measure energy, and is the number trustworthy?**
Energy/carbon is now a board-level concern and a governance signal. We sample real GPU power via NVML, integrate over wall-time, and aggregate in a native C++ engine to Wh, CO2e, and Software Carbon Intensity. The one assumption — grid intensity (475 gCO2e/kWh) — is documented in every artifact. Finding: fp16 is greenest at 0.52 Wh/1k tokens; 8-bit costs 3.4×, 4-bit 1.55×. Command: `make energy-sample`.

## Governance & reliability

**Q: Can a bad model reach production?**
No. Promotion requires tests, metrics, model/data cards, and a passing policy gate evaluated by both an OPA/Rego sketch and a compiled C++ engine. A failing candidate is provably blocked: `make validate-bad`. The carbon-aware gate adds an energy-regression criterion.

**Q: What happens when something breaks?**
Rollback is one command (`make rollback-sample`) and produces a rollback record. The native chaos drill (`make chaos-sample`) injects GPU OOM, slow decode, corrupted weights, and poisoned-candidate scenarios, feeds them into the C++ burn-rate engine, and records an automatic rollback when page thresholds fire.

## Native boundary

**Q: Why not just use Python everywhere?**
Python is the ML lab layer; the production boundary is compiled. C++ engines carry hot paths for policy, image metrics, VTON preprocessing, VTON advanced evaluation/fairness, latency/SLO, burn-rate, energy/carbon, eval statistics, online experiment routing/statistics, static-vs-continuous LLM batch scheduling, model artifact scanning, model provenance verification, semantic-cache lookup, and chaos classification, each with a Python bridge and graceful fallback. Rust owns the Axum gateway, native quota admission, tenant snapshots, and optional Postgres/Valkey-compatible quota mirrors. Go covers the controller/sidecar boundary, including the guardrail sidecar, signed promotion-PR trigger, signed registry-webhook trigger for GitOps/canary deployment actions, and the native load driver that benchmarks Rust vs FastAPI without Python/GIL driver overhead.

## Reproducibility

**Q: Can you reproduce this from scratch?**
`make smoke` runs the Python tests plus every pipeline and native engine offline, and `make native-rust-test` covers 39 Rust gateway quota, durable-ledger, durable-mirror, tenant-snapshot, trace-context, proxy, metrics, auth, static-serving, semantic-cache, and edge-guardrail unit tests. The Go controller/guardrail/benchmark driver and C++ semantic cache are split into reusable modules with their own native tests/smokes. `make gateway-benchmark-native` records the low-level serving evidence without a Python load driver. The GPU tranches are single `make` targets that degrade to the deterministic baseline without a GPU. Every run records code version, dataset version, and hardware.

## Hardest question

**Q: What is the single most production-minded thing here?**
That the platform refuses to lie: it distinguishes real from simulated in a self-audit, blocks unevaluated models, re-baselines SLOs per backend, and overturns its own assumption about quantization with measured energy data. That self-honesty is the difference between a demo and an operating system.
