# Native vLLM Serving Probe

Date: 2026-06-11

## Purpose

This is the production-serving harness for roadmap item E011. It is written in Go and talks to a
vLLM OpenAI-compatible server over HTTP, so the benchmark driver is not a Python client bottleneck.

Research basis:

- vLLM OpenAI-compatible server: https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html
- vLLM quickstart and `vllm serve`: https://docs.vllm.ai/en/stable/getting_started/quickstart.html
- vLLM project: https://github.com/vllm-project/vllm

## Native Implementation

The module is split into focused Go files:

- `native/go/tryops-vllm-probe/config.go`
- `native/go/tryops-vllm-probe/environment.go`
- `native/go/tryops-vllm-probe/http.go`
- `native/go/tryops-vllm-probe/probe.go`
- `native/go/tryops-vllm-probe/jsonutil.go`
- `native/go/tryops-vllm-probe/latency.go`
- `native/go/tryops-vllm-probe/report.go`
- `native/go/tryops-vllm-probe/main.go`
- `native/go/tryops-vllm-probe/probe_test.go`

The probe checks GPU presence, local `vllm` binary availability, `/v1/models`,
`/v1/chat/completions`, and `/metrics`. When a server is live, it also runs a bounded concurrent
load probe and records latency and completion-token throughput.

## Reproduction

Readiness-only local run:

```bash
make native-vllm-probe-test
make llm-vllm-probe-sample
make evaluation-index-sample
```

Live vLLM run:

```bash
vllm serve HuggingFaceTB/SmolLM2-135M-Instruct --host 127.0.0.1 --port 8000
make llm-vllm-probe-sample
```

Primary evidence:

```text
artifacts/eval/llm_vllm/vllm_serving_probe.json
```

## Current Result

The current machine has an NVIDIA L4 with 23,034 MiB GPU memory, but the local `vllm` binary/package
is not installed and no vLLM endpoint is serving at `http://127.0.0.1:8000/v1`. The current report
therefore records `status=skipped`. This is readiness evidence, not a live serving benchmark.
