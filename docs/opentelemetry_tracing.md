# OpenTelemetry-Compatible Tracing

Date: 2026-06-11

## Status

TryOps now emits local OpenTelemetry-compatible API spans without requiring a live Collector in
developer tests.

Implemented artifacts:

- `src/tryops/tracing.py`
- `src/tryops/observability.py`
- `scripts/simulate_tracing.py`
- `infra/otel/collector.yml`
- `native/go/tryops-observability-contract/`
- `artifacts/logs/gateway_events.jsonl`
- `artifacts/eval/traces/trace_sample.json`
- `artifacts/eval/traces/api_spans.jsonl`
- `artifacts/eval/traces/api_events.jsonl`
- `artifacts/eval/observability/native_observability_contract.json`

Validation:

```bash
make trace-sample
make native-observability-contract-sample
```

## Trace Contract

Trace context uses W3C `traceparent` shape:

```text
00-{32_hex_trace_id}-{16_hex_span_id}-{2_hex_flags}
```

Each observed API request receives:

- `trace_id`
- `span_id`
- `parent_span_id` when an upstream `traceparent` is supplied
- `trace_flags`
- `traceparent`

API responses attach a public `trace` object for support correlation. Structured logs include
`trace_id`, `span_id`, and `traceparent`. The span JSONL sink writes `tryops.trace_span.v1` records
to `artifacts/traces/api_spans.jsonl` by default, or to `TRYOPS_TRACE_SPAN_PATH` when configured.

## Span Attributes

Server spans use low-cardinality attributes:

- `http.request.method`
- `http.route`
- `http.response.status_code`
- `service.name`
- `service.version`
- `tryops.request_id`
- `tryops.workload`
- `tryops.model_alias`
- `tryops.model_version`
- `tryops.status`
- `tryops.quota.plan`
- `tryops.user_hash`
- `tryops.llm.prefill_ms`
- `tryops.llm.decode_ms`

The span sink does not store raw prompts, image paths, image bytes, raw user IDs, or uploaded
content.

## Metrics

`GET /v1/metrics` now includes:

- `tryops_trace_spans_total`
- `tryops_trace_span_duration_ms_sum`
- `tryops_trace_span_duration_ms_count`

The labels are endpoint, workload, model alias, and status.

## Production Path

The current implementation has a local span contract, JSONL sinks, OpenTelemetry Collector wiring,
and a native Go verifier for the Collector/Compose/Prometheus/correlation contract. Production
should add live OTLP SDK/exporters from every runtime under sustained load and ship retained logs to
an external durable backend.

The Rust gateway now accepts valid W3C `traceparent`, generates a child gateway span ID, forwards
the trace context to downstream FastAPI, returns `traceparent` plus `x-tryops-trace-id` on proxied
responses, and writes native JSONL envelopes when `TRYOPS_GATEWAY_STRUCTURED_LOG_PATH` is set. The
Python route keeps the same trace contract so local tests and production traffic have the same
correlation shape; live OTLP exporter stitching remains production hardening.

## Research Basis

- OpenTelemetry Trace API and W3C-compatible SpanContext: https://opentelemetry.io/docs/specs/otel/trace/api/
- OpenTelemetry HTTP span semantic conventions: https://opentelemetry.io/docs/specs/semconv/http/http-spans/
- OpenTelemetry Protocol for Collector/exporter delivery: https://opentelemetry.io/docs/specs/otlp/
- OpenTelemetry Collector configuration: https://opentelemetry.io/docs/collector/configuration/
