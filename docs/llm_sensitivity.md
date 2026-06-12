# LLM Length Sensitivity

## Purpose

This benchmark measures how the local LLM evaluation path behaves when prompt length and output limits change. It is a local contract benchmark, not a neural vLLM result.

## Research Basis

Production LLM serving separates prompt prefill from autoregressive decode. Longer prompts increase prefill and KV-cache pressure, while longer generated outputs increase decode work and cache growth. vLLM's PagedAttention paper frames serving efficiency around batching and dynamic KV-cache management, which is why prompt and output length sweeps belong in the optimization report before any model is promoted.

Current source references:

- `https://arxiv.org/abs/2309.06180`
- `https://github.com/vllm-project/vllm`

## Implemented Local Path

The implementation lives in `src/tryops/pipelines/llm_sensitivity.py` and writes schema `tryops.llm_sensitivity.v1`.

The report contains:

- `prompt_length_sensitivity`: generated prompts at target input lengths.
- `output_length_sensitivity`: fixed prompt with varied `max_tokens` limits.
- `summary.prompt_length`: latency and memory aggregates for prompt-length changes.
- `summary.output_length`: latency, memory, observed output tokens, and truncation counts.

## Commands

Run the sample:

```bash
make llm-sensitivity-sample
```

Run manually:

```bash
PYTHONPATH=src python scripts/benchmark_llm_sensitivity.py --output artifacts/eval/llm_sensitivity/sensitivity.json
```

Custom sweep:

```bash
PYTHONPATH=src python scripts/benchmark_llm_sensitivity.py --prompt-length 32 --prompt-length 512 --output-limit 16 --output-limit 128
```

## Limitations

The current adapter is deterministic and CPU-local, so the numbers prove the benchmark harness and reporting contract. They do not prove neural throughput, GPU memory behavior, or live vLLM serving performance. The sensitivity artifact now feeds the native C++ continuous-batching scheduler benchmark in `docs/llm_continuous_batching.md`; real serving claims still require running the same schema against Transformers, vLLM, GPTQ, AWQ, or GGUF variants.
