# Native GGUF CPU Preflight

Date: 2026-06-11

## Purpose

This is the CPU-first LLM artifact gate for roadmap item E010. It validates that a real `.gguf`
model can be downloaded, parsed, classified, and indexed without routing the proof through Python.

Research basis:

- GGUF is the `llama.cpp` model format used for local quantized artifacts and CPU-friendly
  inference workflows: https://github.com/ggml-org/llama.cpp
- Hugging Face documents GGUF loading/conversion support and metadata inspection workflows:
  https://huggingface.co/docs/transformers/main/gguf
- The tested open-source artifact is `bartowski/SmolLM2-135M-Instruct-GGUF`:
  https://huggingface.co/bartowski/SmolLM2-135M-Instruct-GGUF

## Native Implementation

The module is split into focused C++ files:

- `native/cpp/tryops_gguf_preflight/include/tryops_gguf_preflight.hpp`
- `native/cpp/tryops_gguf_preflight/src/tryops_gguf_preflight.cpp`
- `native/cpp/tryops_gguf_preflight/src/tryops_gguf_preflight_cli.cpp`
- `native/cpp/tryops_gguf_preflight/tests/test_gguf_preflight.cpp`

The parser reads GGUF v3 headers, metadata key/value records, tensor descriptors, quantization
file type, tensor type distribution, and selected architecture/tokenizer fields. It also records
whether `llama-cli` is available, but it does not claim generation unless that runtime exists.

## Reproduction

```bash
make native-gguf-preflight-test
make llm-gguf-preflight-sample
make evaluation-index-sample
```

Primary evidence:

```text
artifacts/eval/llm_gguf/gguf_preflight.json
```

Current verified artifact:

- model file: `artifacts/models/gguf/SmolLM2-135M-Instruct-Q2_K.gguf`
- size: 88,202,080 bytes
- GGUF version: 3
- tensors: 272
- metadata entries: 37
- architecture: `llama`
- quantization file type: `mostly_q2_k`
- context length: 8192

## Claim Boundary

This closes the native GGUF preflight path. It does not benchmark live llama.cpp generation because
`llama-cli` is not installed in this workspace. Throughput, quality, and latency claims for GGUF
must wait for a live generation run.
