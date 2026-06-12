# Native GPTQ/AWQ Model Preflight

Date: 2026-06-11

## Purpose

This is the native readiness gate for roadmap items E008 and E009. It verifies that suitable
open-source GPTQ and AWQ model artifacts exist, then checks whether the local runtime can actually
load them.

Research basis:

- Hugging Face Transformers GPTQ quantization: https://huggingface.co/docs/transformers/main/quantization/gptq
- Hugging Face Transformers AWQ quantization: https://huggingface.co/docs/transformers/main/quantization/awq
- GPTQ paper: https://arxiv.org/abs/2210.17323
- AWQ paper: https://arxiv.org/abs/2306.00978

## Native Implementation

The module is split into focused Go files:

- `native/go/tryops-quantized-preflight/config.go`
- `native/go/tryops-quantized-preflight/runtime.go`
- `native/go/tryops-quantized-preflight/hf.go`
- `native/go/tryops-quantized-preflight/probe.go`
- `native/go/tryops-quantized-preflight/jsonutil.go`
- `native/go/tryops-quantized-preflight/report.go`
- `native/go/tryops-quantized-preflight/main.go`
- `native/go/tryops-quantized-preflight/probe_test.go`

It uses direct HTTP against Hugging Face-style `config.json` and `model.safetensors` URLs, parses
`quantization_config`, detects Python loader packages, and records GPU availability.

## Reproduction

```bash
make native-quantized-preflight-test
make llm-quantized-preflight-sample
make evaluation-index-sample
```

Primary evidence:

```text
artifacts/eval/llm_quantized/quantized_model_preflight.json
```

Current verified candidates:

- `Qwen/Qwen2.5-0.5B-Instruct-GPTQ-Int4`: `quant_method=gptq`, 4-bit, group size 128, SafeTensors artifact reachable.
- `Qwen/Qwen2.5-0.5B-Instruct-AWQ`: `quant_method=awq`, 4-bit, group size 128, GEMM/zero-point config, SafeTensors artifact reachable.

## Claim Boundary

The current report is `status=partial`: both candidate repositories are suitable, but live loading
is not ready because `gptqmodel`/`auto_gptq` and `awq`/`autoawq` are not installed. Do not claim
GPTQ/AWQ latency, throughput, memory, or quality until those loader runtimes are installed and a
generation benchmark is run.
