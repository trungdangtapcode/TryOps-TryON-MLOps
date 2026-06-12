# LLM Baseline and Serving Plan

Date: 2026-06-11

## Selected First Model Target

The first open-source neural target is `HuggingFaceTB/SmolLM2-135M-Instruct`.

Reasons:

- It is small enough to be a realistic local baseline before GPU-heavy serving work.
- The model card lists Apache-2.0 licensing.
- The model card includes Transformers, CPU, and vLLM usage paths.
- vLLM can later host the same model behind an OpenAI-compatible serving API.

Primary source: https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct

Source inventory:

- `configs/model_sources.json`
- recorded revision: `12fd25f`
- recorded license: `Apache-2.0`

## Current Local Adapter

The implemented adapter is `tryops-rule-baseline`, a deterministic local baseline in
`src/tryops/pipelines/llm_baseline.py`.

It exists to validate the MLOps path before model weights, CUDA, or vLLM are available:

- safe alias handling: `baseline`, `champion`, `challenger`, `candidate`
- structured JSON output
- prompt class detection for MLOps, quantization, and prompt-injection prompts
- expected-characteristic quality scoring
- prompt-injection and sensitive-disclosure safety flags
- latency, tokens/sec, memory, and cost estimate fields

This is not presented as neural model quality. It is a production-contract baseline that lets
promotion gates, API routing, and benchmark reports run now.

## Reproduction Commands

Run one local response:

```bash
make llm-baseline-sample
```

Run the golden prompt benchmark:

```bash
make llm-benchmark-sample
```

Run prompt/output length sensitivity:

```bash
make llm-sensitivity-sample
```

The benchmark writes:

```text
artifacts/eval/llm_baseline/benchmark.json
```

The length sensitivity benchmark writes:

```text
artifacts/eval/llm_sensitivity/sensitivity.json
```

## API Contract

The local FastAPI route is:

```text
POST /llm/generate
```

Input fields:

- `prompt`: required string
- `model_alias`: safe alias, default `baseline`
- `max_tokens`: bounded integer
- `structured`: boolean, default true

Output fields include:

- `model`: alias, adapter, version, and real model target
- `prompt`: length and prompt class
- `output`: generated text, estimated tokens, truncation flag
- `structured_answer`: machine-readable answer sections when requested
- `metrics`: latency, tokens/sec, memory
- `cost_estimate`: local request and token-cost estimate
- `safety`: injection and credential-disclosure flags

## Optimization Path

The next real variants should use the same benchmark schema:

1. Transformers baseline for `HuggingFaceTB/SmolLM2-135M-Instruct`.
2. vLLM online serving for the same model. The native Go `tryops-vllm-probe` harness is in place; the current local run is skipped because no vLLM endpoint is serving.
3. CPU-first GGUF artifact preflight if GPU access remains weak. The native C++ path now parses a real SmolLM2 Q2_K GGUF artifact; live llama.cpp generation is still pending `llama-cli`.
4. AWQ or GPTQ prequantized variants when compatible with hardware. The native Go preflight now verifies suitable Qwen2.5-0.5B GPTQ/AWQ repos, but live loading needs the missing loader packages.
5. Optional bitsandbytes or llm-compressor paths when CUDA is available.

vLLM's quantization docs list AutoAWQ, BitsAndBytes, GGUF, GPTQModel, LLM Compressor formats,
online quantization, quantized KV cache, and hardware compatibility tables:
https://docs.vllm.ai/en/latest/features/quantization/

The GGUF preflight details are tracked in `docs/llm_gguf.md` and
`artifacts/eval/llm_gguf/gguf_preflight.json`.

The vLLM serving probe details are tracked in `docs/llm_vllm.md` and
`artifacts/eval/llm_vllm/vllm_serving_probe.json`.

The GPTQ/AWQ preflight details are tracked in `docs/llm_quantized.md` and
`artifacts/eval/llm_quantized/quantized_model_preflight.json`.
