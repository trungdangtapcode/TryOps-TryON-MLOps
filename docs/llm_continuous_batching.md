# LLM Continuous Batching

## Purpose

This benchmark proves the local scheduling path for concurrent LLM requests without putting another performance-critical decision in Python. A native C++ CLI compares request-level static batching against iteration-level continuous batching on the same mixed request stream.

## Research Basis

- Orca OSDI 2022 introduced iteration-level scheduling for transformer generation serving: `https://www.usenix.org/conference/osdi22/presentation/yu`
- vLLM documents continuous batching, PagedAttention, chunked prefill, and high-throughput serving as production serving features: `https://docs.vllm.ai/`
- vLLM performance guidance describes decode/prefill scheduling tradeoffs and `max_num_batched_tokens`: `https://docs.vllm.ai/en/v0.4.2/models/performance.html`

## Implemented Local Path

Native engine:

```text
native/cpp/tryops_batch_scheduler/src/tryops_batch_scheduler_cli.cpp
```

Bridge and runner:

```text
src/tryops/native_batch_scheduler.py
scripts/evaluate_continuous_batching.py
```

The Python layer reads the LLM sensitivity artifact, builds a deterministic mixed prompt/decode workload, serializes it to the C++ line protocol, and writes the report. The scheduler comparison itself is native C++.

## Command

```bash
make llm-continuous-batching-sample
```

Artifact:

```text
artifacts/eval/llm_batching/continuous_batching_report.json
```

## Current Evidence

Latest local run:

| Metric | Static batching | Continuous batching |
| --- | ---: | ---: |
| Requests | 20 | 20 |
| Throughput tokens/sec | 5351.802298 | 6519.804866 |
| Latency p95 ms | 119.01 | 96.2476 |
| Decode-slot utilization | 0.623281 | 1.0 |

Comparison:

- Throughput gain: `1.218245x`
- P95 latency reduction: `19.1%`
- Decode-slot utilization gain: `0.376719`

## Limitations

This is native scheduler evidence, not a live vLLM server benchmark. It proves the request-admission and padding-efficiency comparison for a deterministic mixed workload. E011 remains open until vLLM is run against the selected model on compatible hardware with real request traces.
