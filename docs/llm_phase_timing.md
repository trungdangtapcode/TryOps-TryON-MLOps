# LLM Phase Timing

Date: 2026-06-11

TryOps now records LLM prefill/decode phase timing in the generation contract, benchmark reports,
structured logs, and Prometheus metrics.

## Evidence Command

Run:

```bash
make llm-benchmark-sample
```

Primary artifact:

```text
artifacts/eval/llm_baseline/benchmark.json
```

Each record includes:

- `phase_timing.schema_version = tryops.llm_phase_timing.v1`
- `prefill_ms`
- `decode_ms`
- per-phase token rates
- timing source
- timing semantics

The report summary includes average and p95 prefill/decode timing.

## Metrics Surface

`GET /v1/metrics` exposes:

```text
tryops_llm_phase_latency_ms_sum
tryops_llm_phase_latency_ms_count
```

Labels:

- `endpoint`
- `workload`
- `model_alias`
- `phase`

Structured JSONL logs also include `llm_prefill_ms`, `llm_decode_ms`, and
`llm_phase_timing_source`.

## Current Semantics

For the deterministic baseline, prefill is prompt classification and input accounting; decode is
answer rendering and truncation. This is a contract-level local split, not a neural kernel trace.

For Transformers-backed inference, TryOps records prompt preparation separately and records
`model.generate` wall time as a decode proxy. The low-level internal model prefill/decode split
should come from vLLM or a lower-level serving tracer when that backend is installed.

## Research Basis

The vLLM PagedAttention paper motivates separating serving behavior around prompt processing,
dynamic KV cache growth, batching, and decode throughput. vLLM's chunked prefill and continuous
batching path is the production target for stronger phase telemetry.

References:

- vLLM PagedAttention paper: https://arxiv.org/abs/2309.06180
- vLLM project: https://github.com/vllm-project/vllm
