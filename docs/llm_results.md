# LLM Baseline Results

Date: 2026-06-11

## Run

Command:

```bash
make llm-benchmark-sample
```

Artifact:

```text
artifacts/eval/llm_baseline/benchmark.json
```

Length sensitivity artifact:

```text
artifacts/eval/llm_sensitivity/sensitivity.json
```

Optimization report artifacts:

```text
artifacts/eval/llm_optimization_report/llm_optimization_report.md
artifacts/eval/llm_optimization_report/llm_pareto_chart.svg
artifacts/eval/llm_optimization_report/llm_pareto_metrics.csv
```

Prompt set:

```text
samples/eval/golden_prompts.json
```

## Current Baseline Summary

Adapter: `tryops-rule-baseline`

Real model target: `HuggingFaceTB/SmolLM2-135M-Instruct`

| Metric | Value |
| --- | ---: |
| Quality score | 1.0 |
| Latency p95 ms | 0.026 |
| Tokens/sec | 46666.666667 |
| Memory GB | 0.016907 |
| Estimated request cost USD | 0.0 |

## Phase Timing Summary

Schema: `tryops.llm_phase_timing.v1`

| Metric | Value |
| --- | ---: |
| Prefill avg ms | 0.00594 |
| Prefill p95 ms | 0.007464 |
| Decode avg ms | 0.014925 |
| Decode p95 ms | 0.018298 |

The deterministic baseline phase split is a local contract metric: prefill covers prompt
classification and input accounting, while decode covers deterministic answer rendering and output
truncation. Real serving should replace the proxy with lower-level vLLM or backend phase telemetry.

The score is deterministic because this adapter is a rules baseline. It validates that the
evaluation harness can detect required characteristics and safety behavior before replacing the
adapter with Transformers or vLLM.

## Prompt Coverage

The golden prompt set currently covers:

- MLOps project summary requirements
- prompt-injection and hidden-credential refusal behavior
- GPTQ versus AWQ benchmark explanation requirements

## Limitations

- The baseline run itself is deterministic; real neural and quantized measurements are tracked in the separate `llm_real` and `llm_pareto` artifacts.
- The current latency and throughput values are local contract timings, not vLLM serving timings. The native Go vLLM probe is ready, but the current artifact is skipped because no vLLM endpoint is serving locally.
- Prompt and output length sensitivity are now measured for the local baseline only.
- The current Pareto report covers fp16-style, bitsandbytes 8-bit, and bitsandbytes 4-bit variants only. Native C++ GGUF artifact preflight and native Go GPTQ/AWQ candidate preflight are tracked separately and are not throughput/quality benchmarks.

## Next Measurements

The next LLM optimization run should add:

- vLLM serving if the environment has compatible dependencies and hardware
- live AWQ/GPTQModel loading or live llama.cpp GGUF generation depending on hardware and installed runtime availability
- concurrent request tests for batching behavior
