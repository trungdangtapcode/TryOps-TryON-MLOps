package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestEvaluateObservabilityContract(t *testing.T) {
	root := t.TempDir()
	writeFile(t, root, "infra/otel/collector.yml", `
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  filelog/tryops:
    include:
      - /var/log/tryops/*.jsonl
processors:
  memory_limiter: {}
  resource/tryops: {}
  batch: {}
exporters:
  debug: {}
  file/traces:
    path: /var/lib/tryops/otel/traces.jsonl
  file/logs:
    path: /var/lib/tryops/otel/logs.jsonl
  file/metrics:
    path: /var/lib/tryops/otel/metrics.jsonl
extensions:
  health_check:
    endpoint: 0.0.0.0:13133
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resource/tryops, batch]
      exporters: [debug, file/traces]
    logs:
      receivers: [otlp, filelog/tryops]
      processors: [memory_limiter, resource/tryops, batch]
      exporters: [debug, file/logs]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, resource/tryops, batch]
      exporters: [debug, file/metrics]
`)
	writeFile(t, root, "docker-compose.yml", `
services:
  prometheus:
    image: prom/prometheus:latest
    depends_on:
      otel-collector:
        condition: service_started
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports:
      - "${TRYOPS_OTEL_GRPC_PORT:-4317}:4317"
      - "${TRYOPS_OTEL_HTTP_PORT:-4318}:4318"
      - "${TRYOPS_OTEL_METRICS_PORT:-8888}:8888"
    volumes:
      - ./infra/otel/collector.yml:/etc/otelcol-contrib/config.yml:ro
      - ./artifacts/logs:/var/log/tryops:ro
    healthcheck:
      test: ["CMD", "/otelcol-contrib", "validate", "--config=/etc/otelcol-contrib/config.yml"]
`)
	writeFile(t, root, "infra/prometheus/prometheus.yml", `
rule_files:
  - /etc/prometheus/tryops_alerts.yml
  - /etc/prometheus/tryops_burn_rate_alerts.yml
  - /etc/prometheus/tryops_finops_alerts.yml
scrape_configs:
  - job_name: tryops-otel-collector
    static_configs:
      - targets: ["otel-collector:8888"]
`)
	writeFile(t, root, "artifacts/eval/traces/trace_sample.json", `{
  "schema_version": "tryops.trace_sample.v1",
  "events": [{"workload": "llm", "model_alias": "baseline"}]
}`)
	writeFile(t, root, "artifacts/eval/traces/api_spans.jsonl", `{"trace_id":"11111111111111111111111111111111","span_id":"2222222222222222"}`+"\n")
	writeFile(t, root, "artifacts/eval/traces/api_events.jsonl", `{"trace_id":"11111111111111111111111111111111","span_id":"2222222222222222","severity_text":"INFO","severity_number":9,"resource":{"service.name":"tryops-api"},"attributes":{"workload":"llm","model_alias":"baseline"},"native_envelope":{"schema_version":"tryops.native_trace_log_envelope.v1","resource":{"service.name":"tryops-api"}}}`+"\n")
	writeFile(t, root, "artifacts/logs/gateway_events.jsonl", `{"schema_version":"tryops.native_trace_log_envelope.v1","trace_id":"11111111111111111111111111111111","span_id":"3333333333333333","resource":{"service.name":"tryops-gateway"},"attributes":{"endpoint":"/v1/llm/generate"}}`+"\n")

	report, err := evaluate(Config{
		Root:            root,
		CollectorPath:   "infra/otel/collector.yml",
		ComposePath:     "docker-compose.yml",
		PrometheusPath:  "infra/prometheus/prometheus.yml",
		TraceSamplePath: "artifacts/eval/traces/trace_sample.json",
		APISpanPath:     "artifacts/eval/traces/api_spans.jsonl",
		APILogPath:      "artifacts/eval/traces/api_events.jsonl",
		GatewayLogPath:  "artifacts/logs/gateway_events.jsonl",
		CoverageLevel:   "partial",
	})
	if err != nil {
		t.Fatal(err)
	}
	if !report.Passed {
		t.Fatalf("expected pass: %#v", report.Checks)
	}
	if report.Summary.CorrelatedTraces != 1 || report.Summary.StructuredLogs != 2 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
	if !report.Correlation.ModelCallObserved {
		t.Fatalf("expected model call observation")
	}
}

func writeFile(t *testing.T, root string, path string, content string) {
	t.Helper()
	fullPath := filepath.Join(root, path)
	if err := os.MkdirAll(filepath.Dir(fullPath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(fullPath, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}
