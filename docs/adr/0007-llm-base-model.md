# ADR 0007: LLM Base Model and Optimization Strategy

## Status

Accepted.

## Decision

TryOps will start with `HuggingFaceTB/SmolLM2-135M-Instruct` as the first small open-source instruct-model target, then compare baseline serving against quantized or optimized variants.

The current executable local adapter is `tryops-rule-baseline`, a deterministic dependency-free baseline used to validate the API, benchmark, safety, and promotion contracts before model weights are downloaded.

Preferred serving path:

1. Dependency-free local baseline for contract verification.
2. Baseline Transformers inference for neural-model correctness.
3. vLLM for optimized serving if hardware supports it.
4. GGUF/llama.cpp-style CPU fallback if GPU support is weak.
5. AWQ or GPTQ prequantized variants when compatible.

## Rationale

The project goal is not to train an LLM. The goal is to show MLOps evaluation, benchmarking, model routing, and promotion gates around LLM optimization.

## Consequences

- The benchmark must measure latency, tokens/sec, memory, quality, and cost estimate.
- A quantized model cannot be promoted if quality falls below the policy threshold.
- The UI should show quality/latency/memory tradeoffs, not only generated text.
- The rules baseline cannot be used as evidence of neural model quality; it only proves the MLOps contract.
