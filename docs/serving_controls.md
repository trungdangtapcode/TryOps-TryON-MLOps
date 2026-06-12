# Serving Controls

Date: 2026-06-11

TryOps now has executable serving controls for long-running inference:

- per-request `timeout_ms`
- timeout structured errors with `error.code=timeout_exceeded`
- async VTON job submission and status lookup
- Prometheus-compatible async queue-depth metric
- privacy-aware LLM semantic-cache lookup before generation
- endpoint smoke report for readiness, LLM generation, VTON inference, and metrics

## Research Notes

FastAPI documents background work as useful when the client should receive an accepted response
before slower processing finishes:
https://fastapi.tiangolo.com/tutorial/background-tasks/

The same FastAPI page cautions that heavy computation across processes or servers should move to a
larger queue system such as Celery with RabbitMQ or Redis:
https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat

Kubernetes documents readiness, liveness, and startup probes as separate controls for sending
traffic only to ready pods and for handling slow startup:
https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

## Local API Contract

Synchronous inference requests accept `timeout_ms`, defaulting to 30,000 ms and capped at 300,000 ms.
If the local operation exceeds the deadline, the API returns:

```json
{
  "status": "rejected",
  "error": {
    "code": "timeout_exceeded"
  }
}
```

VTON also has a local async path:

- `POST /v1/vton/jobs`: validate and enqueue a VTON payload
- `GET /v1/vton/jobs/{job_id}`: read current status and final result

The local job queue is in memory and dependency-free. It is appropriate for smoke tests and product
contract evidence, not for production durability.

LLM generation also has a local semantic-cache path:

- guardrails and quota run first
- the cache checks a model-scoped prompt fingerprint
- PII-redacted prompts are not stored
- hits skip generation and report saved tokens/cost/energy

## Endpoint Smoke Evidence

Run:

```bash
make endpoint-smoke-sample
```

Artifact:

```text
artifacts/eval/endpoint_smoke/deployed_endpoint_smoke.json
```

The smoke runner verifies the local `/v1` serving contract end to end: readiness, LLM generation,
VTON inference against deterministic PNG inputs, and Prometheus-compatible metrics after both
inference paths run. It also accepts `--base-url` for a deployed API when the stack is running.

## Production Path

Production should move the same contract into lower-level or distributed components:

- Rust gateway for request admission, deadline propagation, and early timeout rejection
- Rust gateway for semantic-cache admission and configured C++ CLI/vector-service lookup
- Go controller for job reconciliation and status ownership
- Redis, RabbitMQ, or another queue layer for durable async dispatch
- Kubernetes readiness/startup probes for traffic safety during model load
- Prometheus queue-depth, timeout, and job failure alerts
