package main

import (
	"strings"
	"testing"
)

func TestParseAPISpan(t *testing.T) {
	line := []byte(`{
		"schema_version":"tryops.trace_span.v1",
		"trace_id":"11111111111111111111111111111111",
		"span_id":"2222222222222222",
		"parent_span_id":null,
		"name":"POST /v1/vton/infer",
		"start_time":"2026-06-13T12:00:00.000000Z",
		"end_time":"2026-06-13T12:00:01.500000Z",
		"resource":{"service.name":"tryops-api","service.version":"0.1.0"},
		"attributes":{"http.route":"/v1/vton/infer","tryops.request_id":"req-test"},
		"status":{"code":"UNSET","message":"completed"}
	}`)

	span, ok := parseTryOpsSpan(line)
	if !ok {
		t.Fatal("expected API span to parse")
	}
	if span.TraceID != "11111111111111111111111111111111" || span.SpanID != "2222222222222222" {
		t.Fatalf("unexpected identifiers: trace=%s span=%s", span.TraceID, span.SpanID)
	}
	if span.Name != "POST /v1/vton/infer" {
		t.Fatalf("unexpected span name: %s", span.Name)
	}
	if got := stringFromMap(span.Resource, "service.name", ""); got != "tryops-api" {
		t.Fatalf("unexpected service name: %s", got)
	}
	if span.StartTimeUnixNano == "" || span.EndTimeUnixNano == "" {
		t.Fatal("expected start/end timestamps")
	}
}

func TestParseNativeEnvelope(t *testing.T) {
	line := []byte(`{
		"schema_version":"tryops.native_trace_log_envelope.v1",
		"trace_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		"span_id":"bbbbbbbbbbbbbbbb",
		"observed_timestamp":1781382875062,
		"event_name":"gateway_proxy",
		"request_id":"req-gateway",
		"workload":"vton",
		"component":"gateway",
		"resource":{"service.name":"tryops-gateway"},
		"attributes":{"method":"GET","endpoint":"/api/account/jobs","status":200,"latency_ms":25.5}
	}`)

	span, ok := parseTryOpsSpan(line)
	if !ok {
		t.Fatal("expected native envelope to parse")
	}
	if span.TraceID != "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" || span.SpanID != "bbbbbbbbbbbbbbbb" {
		t.Fatalf("unexpected identifiers: trace=%s span=%s", span.TraceID, span.SpanID)
	}
	if span.Name != "GET /api/account/jobs" {
		t.Fatalf("unexpected span name: %s", span.Name)
	}
	if got := stringFromMap(span.Resource, "service.name", ""); got != "tryops-gateway" {
		t.Fatalf("unexpected service name: %s", got)
	}
	if span.Status["code"] != 0 {
		t.Fatalf("unexpected status: %#v", span.Status)
	}
}

func TestBridgeMetricsRender(t *testing.T) {
	metrics := newBridgeMetrics()
	metrics.recordLine("/tmp/api_spans.jsonl", "parsed")
	metrics.recordSpan("tryops-api")
	metrics.recordExportFailure()
	metrics.setOffset("/tmp/api_spans.jsonl", 128)

	rendered := metrics.render()
	for _, expected := range []string{
		`tryops_otel_bridge_lines_total{source="/tmp/api_spans.jsonl",status="parsed"} 1`,
		`tryops_otel_bridge_spans_total{service="tryops-api"} 1`,
		`tryops_otel_bridge_export_failures_total 1`,
		`tryops_otel_bridge_file_offset_bytes{path="/tmp/api_spans.jsonl"} 128`,
	} {
		if !strings.Contains(rendered, expected) {
			t.Fatalf("missing metric %q in:\n%s", expected, rendered)
		}
	}
}
