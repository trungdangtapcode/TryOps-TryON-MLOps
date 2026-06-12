# LLM Runtime Guardrails

Date: 2026-06-11

TryOps now enforces an LLM guardrail layer at the Rust gateway edge and again inside
`/v1/llm/generate`. The production path is a native Go sidecar exposed over HTTP; the CLI and
Python paths keep local evaluation deterministic when the sidecar is not running.

## Runtime Path

Ingress checks run before generation. In the product stack, the Rust gateway calls the native Go
sidecar before proxying `/api/llm/generate`; the FastAPI backend keeps the same guardrail contract
before routing, quota accounting, and generation:

- Presidio-style deterministic PII masking replaces emails, phone numbers, SSNs, payment-card-like values, API keys, and secret assignments with scoped placeholders.
- A native Go sidecar or CLI blocks prompt injection, system-prompt leakage, secret disclosure, unbounded consumption, and unsafe agency requests.
- `TRYOPS_GUARDRAIL_URL` points the API at the native HTTP sidecar.
- `TRYOPS_GATEWAY_GUARDRAIL_URL` points the Rust gateway at the same native HTTP sidecar for edge enforcement.
- `TRYOPS_NATIVE_GUARDRAIL_CLI` points batch/offline evaluation at the native CLI.
- If neither native path is available, `src/tryops/guardrails.py` uses the same deterministic fallback so local smoke remains offline.

Egress checks run before the API response is returned:

- Generated text is scanned for credential-like material and hidden prompt markers.
- Structured output is validated when `structured=true`.
- PII placeholders can be restored at egress if the model echoed a placeholder; the public guardrail verdict never includes the original PII values.

## Native Boundary

Native classifier and sidecar:

```text
native/go/tryops-guardrail
```

Build and evaluate:

```bash
make guardrail-sample
make native-guardrail-test
make native-guardrail-smoke
make native-edge-guardrail-smoke
```

Artifacts:

- `artifacts/native/tryops_guardrail_cli`
- `artifacts/native/tryops_guardrail_server.log`
- `artifacts/eval/guardrails/guardrail_report.json`

HTTP endpoints:

- `GET /health`
- `POST /v1/guardrails/evaluate`
- `GET /metrics`

Docker Compose runs this as an independent `guardrail` service and sets both the API's
`TRYOPS_GUARDRAIL_URL` and the gateway's `TRYOPS_GATEWAY_GUARDRAIL_URL` to
`http://guardrail:18083/v1/guardrails/evaluate`.

Schemas:

- `tryops.native_guardrail.v1`
- `tryops.guardrail_verdict.v1`
- `tryops.guardrail_report.v1`

## OWASP LLM 2025 Coverage

The runtime layer maps controls to these OWASP Top 10 for LLM Applications 2025 risks:

| OWASP ID | Runtime Control |
| --- | --- |
| `LLM01:2025` | prompt-injection classifier |
| `LLM02:2025` | PII redaction and secret-disclosure blocks |
| `LLM05:2025` | structured-output schema validator |
| `LLM06:2025` | unsafe-agency classifier |
| `LLM07:2025` | system/developer prompt leakage classifier |
| `LLM10:2025` | unbounded-output and max-token guard |

`configs/governance_risk_controls.json` retains the full OWASP LLM 2025 map for all ten risks.

## Promotion Gate

LLM promotion candidates must carry a `guardrail_report` artifact and guardrail metadata:

```json
{
  "guardrails": {
    "status": "passed",
    "failed_cases": 0,
    "blocked_risk_ids": []
  }
}
```

The gate rejects candidates with a missing report, failed guardrail probes, or a blocked egress leak verdict such as `LLM07:2025`.

## Observability

The API emits guardrail counters through `/v1/metrics`:

```text
tryops_guardrail_events_total{owasp_id="LLM07:2025",action="block",status="rejected"}
```

The native sidecar also emits its own low-level Prometheus counters:

```text
tryops_native_guardrail_requests_total{status="blocked"}
tryops_native_guardrail_findings_total{owasp_id="LLM07:2025",action="block"}
```

The Rust gateway emits edge-enforcement counters when `TRYOPS_GATEWAY_GUARDRAIL_URL` is configured:

```text
tryops_gateway_guardrail_decisions_total{status="blocked"}
```

Grafana dashboard:

```text
infra/grafana/dashboards/tryops-guardrails.json
```

The dashboard includes blocked requests by OWASP risk, actions by risk, and a guardrail evidence table.

## Research Basis

- OWASP GenAI Security Project lists the 2025 LLM risks, including Prompt Injection, Sensitive Information Disclosure, Improper Output Handling, Excessive Agency, System Prompt Leakage, and Unbounded Consumption: https://genai.owasp.org/llm-top-10/
- Microsoft Presidio is an open-source framework for detecting and anonymizing PII across text and other data: https://github.com/microsoft/presidio
- Meta Prompt Guard is a classifier for benign, injection, and jailbreak inputs and recommends layering model-based protection with additional controls: https://huggingface.co/meta-llama/Prompt-Guard-86M
- Meta Llama Guard 3 is positioned as an input/output safeguard model for LLM conversations, with documented use through Transformers, vLLM, and SGLang: https://huggingface.co/meta-llama/Llama-Guard-3-8B
- NVIDIA NeMo Guardrails provides programmable guardrails for LLM applications and uses Colang to model controllable dialogue flows: https://github.com/NVIDIA-NeMo/Guardrails
