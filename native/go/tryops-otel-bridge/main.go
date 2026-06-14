package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	apiSpanSchema        = "tryops.trace_span.v1"
	nativeEnvelopeSchema = "tryops.native_trace_log_envelope.v1"
)

type bridge struct {
	files       []string
	exportURL   string
	startAtEnd  bool
	pollEvery   time.Duration
	httpClient  *http.Client
	metrics     *bridgeMetrics
	fileOffsets map[string]int64
	mu          sync.Mutex
}

type bridgeMetrics struct {
	mu             sync.Mutex
	lines          map[string]map[string]uint64
	spans          map[string]uint64
	exportFailures uint64
	lastExportUnix int64
	fileOffsets    map[string]int64
}

type otlpSpan struct {
	TraceID           string         `json:"traceId"`
	SpanID            string         `json:"spanId"`
	ParentSpanID      string         `json:"parentSpanId,omitempty"`
	Name              string         `json:"name"`
	Kind              int            `json:"kind"`
	StartTimeUnixNano string         `json:"startTimeUnixNano"`
	EndTimeUnixNano   string         `json:"endTimeUnixNano"`
	Attributes        []otlpKeyValue `json:"attributes,omitempty"`
	Status            map[string]any `json:"status,omitempty"`
	Resource          map[string]any `json:"-"`
}

type otlpKeyValue struct {
	Key   string       `json:"key"`
	Value otlpAnyValue `json:"value"`
}

type otlpAnyValue struct {
	StringValue string  `json:"stringValue,omitempty"`
	IntValue    string  `json:"intValue,omitempty"`
	DoubleValue float64 `json:"doubleValue,omitempty"`
	BoolValue   *bool   `json:"boolValue,omitempty"`
}

func main() {
	addr := getenv("TRYOPS_OTEL_BRIDGE_ADDR", ":19122")
	files := splitCSV(getenv("TRYOPS_OTEL_BRIDGE_TRACE_FILES", "/var/lib/tryops/traces/api_spans.jsonl,/var/log/tryops/gateway_events.jsonl"))
	exportURL := getenv("TRYOPS_OTEL_BRIDGE_OTLP_TRACES_URL", "http://otel-collector:4318/v1/traces")
	startAtEnd := strings.EqualFold(getenv("TRYOPS_OTEL_BRIDGE_START_AT", "end"), "end")

	b := &bridge{
		files:       files,
		exportURL:   exportURL,
		startAtEnd:  startAtEnd,
		pollEvery:   2 * time.Second,
		httpClient:  &http.Client{Timeout: 5 * time.Second},
		metrics:     newBridgeMetrics(),
		fileOffsets: map[string]int64{},
	}
	b.initOffsets()
	go b.run()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "service": "tryops-otel-bridge"})
	})
	mux.HandleFunc("/metrics", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		_, _ = w.Write([]byte(b.metrics.render()))
	})

	log.Printf("tryops-otel-bridge listening on %s; exporting traces to %s", addr, exportURL)
	if err := http.ListenAndServe(addr, mux); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}

func (b *bridge) initOffsets() {
	for _, path := range b.files {
		var offset int64
		if b.startAtEnd {
			if stat, err := os.Stat(path); err == nil {
				offset = stat.Size()
			}
		}
		b.fileOffsets[path] = offset
		b.metrics.setOffset(path, offset)
	}
}

func (b *bridge) run() {
	ticker := time.NewTicker(b.pollEvery)
	defer ticker.Stop()
	for {
		for _, path := range b.files {
			b.pollFile(path)
		}
		<-ticker.C
	}
}

func (b *bridge) pollFile(path string) {
	file, err := os.Open(path)
	if err != nil {
		b.metrics.recordLine(path, "missing")
		return
	}
	defer file.Close()

	b.mu.Lock()
	offset := b.fileOffsets[path]
	b.mu.Unlock()

	if _, err := file.Seek(offset, io.SeekStart); err != nil {
		b.metrics.recordLine(path, "seek_error")
		return
	}
	reader := bufio.NewReader(file)
	for {
		chunk, err := reader.ReadString('\n')
		if len(chunk) > 0 {
			offset += int64(len(chunk))
			b.handleLine(path, strings.TrimSpace(chunk))
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			b.metrics.recordLine(path, "read_error")
			break
		}
	}

	b.mu.Lock()
	b.fileOffsets[path] = offset
	b.mu.Unlock()
	b.metrics.setOffset(path, offset)
}

func (b *bridge) handleLine(path string, line string) {
	if line == "" {
		return
	}
	span, ok := parseTryOpsSpan([]byte(line))
	if !ok {
		b.metrics.recordLine(path, "dropped")
		return
	}
	if err := b.export(span); err != nil {
		b.metrics.recordLine(path, "export_failed")
		b.metrics.recordExportFailure()
		return
	}
	serviceName := stringFromMap(span.Resource, "service.name", "unknown")
	b.metrics.recordLine(path, "parsed")
	b.metrics.recordSpan(serviceName)
}

func (b *bridge) export(span otlpSpan) error {
	body := map[string]any{
		"resourceSpans": []any{
			map[string]any{
				"resource": map[string]any{
					"attributes": otlpAttributes(span.Resource),
				},
				"scopeSpans": []any{
					map[string]any{
						"scope": map[string]any{"name": "tryops-otel-bridge", "version": "0.1.0"},
						"spans": []otlpSpan{span},
					},
				},
			},
		},
	}
	encoded, err := json.Marshal(body)
	if err != nil {
		return err
	}
	request, err := http.NewRequest(http.MethodPost, b.exportURL, bytes.NewReader(encoded))
	if err != nil {
		return err
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := b.httpClient.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("otlp export failed: %s", response.Status)
	}
	b.metrics.recordExport()
	return nil
}

func parseTryOpsSpan(line []byte) (otlpSpan, bool) {
	var payload map[string]any
	if err := json.Unmarshal(line, &payload); err != nil {
		return otlpSpan{}, false
	}
	switch fmt.Sprint(payload["schema_version"]) {
	case apiSpanSchema:
		return parseAPISpan(payload)
	case nativeEnvelopeSchema:
		return parseNativeEnvelope(payload)
	default:
		return otlpSpan{}, false
	}
}

func parseAPISpan(payload map[string]any) (otlpSpan, bool) {
	traceID := hexID(payload["trace_id"], 32)
	spanID := hexID(payload["span_id"], 16)
	if traceID == "" || spanID == "" {
		return otlpSpan{}, false
	}
	start := parseTimeNano(payload["start_time"], time.Now().UnixNano())
	end := parseTimeNano(payload["end_time"], start)
	if end < start {
		end = start
	}
	resource := mapValue(payload["resource"])
	attrs := otlpAttributes(mapValue(payload["attributes"]))
	status := statusValue(payload)
	return otlpSpan{
		TraceID:           traceID,
		SpanID:            spanID,
		ParentSpanID:      hexID(payload["parent_span_id"], 16),
		Name:              stringValue(payload["name"], "tryops api span"),
		Kind:              2,
		StartTimeUnixNano: strconv.FormatInt(start, 10),
		EndTimeUnixNano:   strconv.FormatInt(end, 10),
		Attributes:        attrs,
		Status:            status,
		Resource:          resource,
	}, true
}

func parseNativeEnvelope(payload map[string]any) (otlpSpan, bool) {
	traceID := hexID(payload["trace_id"], 32)
	spanID := hexID(payload["span_id"], 16)
	if traceID == "" || spanID == "" {
		return otlpSpan{}, false
	}
	attrsMap := mapValue(payload["attributes"])
	end := parseTimeNano(payload["observed_timestamp"], time.Now().UnixNano())
	latencyMs := floatValue(attrsMap["latency_ms"], 0)
	start := end - int64(latencyMs*1_000_000)
	if start <= 0 {
		start = end
	}
	method := stringFromMap(attrsMap, "method", "GET")
	endpoint := stringFromMap(attrsMap, "endpoint", stringValue(payload["event_name"], "tryops.gateway"))
	name := strings.TrimSpace(method + " " + endpoint)
	resource := mapValue(payload["resource"])
	if len(resource) == 0 {
		resource = map[string]any{"service.name": "tryops-gateway"}
	}
	attrsMap["tryops.request_id"] = payload["request_id"]
	attrsMap["tryops.workload"] = payload["workload"]
	attrsMap["tryops.component"] = payload["component"]
	return otlpSpan{
		TraceID:           traceID,
		SpanID:            spanID,
		Name:              name,
		Kind:              2,
		StartTimeUnixNano: strconv.FormatInt(start, 10),
		EndTimeUnixNano:   strconv.FormatInt(end, 10),
		Attributes:        otlpAttributes(attrsMap),
		Status:            map[string]any{"code": statusCodeFromHTTP(attrsMap["status"])},
		Resource:          resource,
	}, true
}

func statusValue(payload map[string]any) map[string]any {
	status := mapValue(payload["status"])
	code := strings.ToUpper(stringFromMap(status, "code", "UNSET"))
	message := stringFromMap(status, "message", "")
	otlpCode := 0
	if code == "ERROR" {
		otlpCode = 2
	}
	return map[string]any{"code": otlpCode, "message": message}
}

func statusCodeFromHTTP(value any) int {
	status, _ := strconv.Atoi(strings.TrimSpace(fmt.Sprint(value)))
	if status >= 500 {
		return 2
	}
	return 0
}

func parseTimeNano(value any, fallback int64) int64 {
	text := strings.TrimSpace(fmt.Sprint(value))
	if text == "" || text == "<nil>" {
		return fallback
	}
	if unix, err := strconv.ParseInt(text, 10, 64); err == nil {
		switch {
		case unix > 1_000_000_000_000_000_000:
			return unix
		case unix > 1_000_000_000_000:
			return unix * 1_000_000
		case unix > 1_000_000_000:
			return unix * 1_000_000_000
		default:
			return fallback
		}
	}
	if parsed, err := time.Parse(time.RFC3339Nano, text); err == nil {
		return parsed.UnixNano()
	}
	return fallback
}

func otlpAttributes(values map[string]any) []otlpKeyValue {
	keys := make([]string, 0, len(values))
	for key := range values {
		if strings.TrimSpace(key) != "" {
			keys = append(keys, key)
		}
	}
	sortStrings(keys)
	attrs := make([]otlpKeyValue, 0, len(keys))
	for _, key := range keys {
		attrs = append(attrs, otlpKeyValue{Key: key, Value: otlpValue(values[key])})
	}
	return attrs
}

func otlpValue(value any) otlpAnyValue {
	switch v := value.(type) {
	case bool:
		return otlpAnyValue{BoolValue: &v}
	case float64:
		if v == float64(int64(v)) {
			return otlpAnyValue{IntValue: strconv.FormatInt(int64(v), 10)}
		}
		return otlpAnyValue{DoubleValue: v}
	case int:
		return otlpAnyValue{IntValue: strconv.Itoa(v)}
	case int64:
		return otlpAnyValue{IntValue: strconv.FormatInt(v, 10)}
	case string:
		return otlpAnyValue{StringValue: v}
	case nil:
		return otlpAnyValue{StringValue: ""}
	default:
		encoded, err := json.Marshal(v)
		if err != nil {
			return otlpAnyValue{StringValue: fmt.Sprint(v)}
		}
		return otlpAnyValue{StringValue: string(encoded)}
	}
}

func mapValue(value any) map[string]any {
	if typed, ok := value.(map[string]any); ok {
		return typed
	}
	return map[string]any{}
}

func stringFromMap(values map[string]any, key string, fallback string) string {
	return stringValue(values[key], fallback)
}

func stringValue(value any, fallback string) string {
	text := strings.TrimSpace(fmt.Sprint(value))
	if text == "" || text == "<nil>" {
		return fallback
	}
	return text
}

func floatValue(value any, fallback float64) float64 {
	switch v := value.(type) {
	case float64:
		return v
	case string:
		parsed, err := strconv.ParseFloat(v, 64)
		if err == nil {
			return parsed
		}
	}
	return fallback
}

func hexID(value any, length int) string {
	text := strings.ToLower(strings.TrimSpace(fmt.Sprint(value)))
	if text == "" || text == "<nil>" || len(text) != length {
		return ""
	}
	for _, ch := range text {
		if !((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f')) {
			return ""
		}
	}
	return text
}

func splitCSV(value string) []string {
	parts := strings.Split(value, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			out = append(out, trimmed)
		}
	}
	return out
}

func getenv(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func newBridgeMetrics() *bridgeMetrics {
	return &bridgeMetrics{
		lines:       map[string]map[string]uint64{},
		spans:       map[string]uint64{},
		fileOffsets: map[string]int64{},
	}
}

func (m *bridgeMetrics) recordLine(source string, status string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.lines[source]; !ok {
		m.lines[source] = map[string]uint64{}
	}
	m.lines[source][status]++
}

func (m *bridgeMetrics) recordSpan(service string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.spans[service]++
}

func (m *bridgeMetrics) recordExportFailure() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.exportFailures++
}

func (m *bridgeMetrics) recordExport() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.lastExportUnix = time.Now().Unix()
}

func (m *bridgeMetrics) setOffset(path string, offset int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.fileOffsets[path] = offset
}

func (m *bridgeMetrics) render() string {
	m.mu.Lock()
	defer m.mu.Unlock()
	var b strings.Builder
	b.WriteString("# HELP tryops_otel_bridge_lines_total JSONL lines processed by source and status.\n")
	b.WriteString("# TYPE tryops_otel_bridge_lines_total counter\n")
	for _, source := range sortedMapKeys(m.lines) {
		for _, status := range sortedUintKeys(m.lines[source]) {
			fmt.Fprintf(&b, "tryops_otel_bridge_lines_total{source=%q,status=%q} %d\n", label(source), label(status), m.lines[source][status])
		}
	}
	b.WriteString("# HELP tryops_otel_bridge_spans_total Spans exported by service name.\n")
	b.WriteString("# TYPE tryops_otel_bridge_spans_total counter\n")
	for _, service := range sortedUintKeys(m.spans) {
		fmt.Fprintf(&b, "tryops_otel_bridge_spans_total{service=%q} %d\n", label(service), m.spans[service])
	}
	b.WriteString("# HELP tryops_otel_bridge_export_failures_total Failed OTLP trace exports.\n")
	b.WriteString("# TYPE tryops_otel_bridge_export_failures_total counter\n")
	fmt.Fprintf(&b, "tryops_otel_bridge_export_failures_total %d\n", m.exportFailures)
	b.WriteString("# HELP tryops_otel_bridge_last_export_unixtime Last successful OTLP export Unix timestamp.\n")
	b.WriteString("# TYPE tryops_otel_bridge_last_export_unixtime gauge\n")
	fmt.Fprintf(&b, "tryops_otel_bridge_last_export_unixtime %d\n", m.lastExportUnix)
	b.WriteString("# HELP tryops_otel_bridge_file_offset_bytes Last read offset for each tailed file.\n")
	b.WriteString("# TYPE tryops_otel_bridge_file_offset_bytes gauge\n")
	for _, path := range sortedIntKeys(m.fileOffsets) {
		fmt.Fprintf(&b, "tryops_otel_bridge_file_offset_bytes{path=%q} %d\n", label(path), m.fileOffsets[path])
	}
	return b.String()
}

func sortedMapKeys(values map[string]map[string]uint64) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sortStrings(keys)
	return keys
}

func sortedUintKeys(values map[string]uint64) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sortStrings(keys)
	return keys
}

func sortedIntKeys(values map[string]int64) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sortStrings(keys)
	return keys
}

func sortStrings(values []string) {
	for i := 0; i < len(values); i++ {
		for j := i + 1; j < len(values); j++ {
			if values[j] < values[i] {
				values[i], values[j] = values[j], values[i]
			}
		}
	}
}

func label(value string) string {
	return strings.ReplaceAll(strings.ReplaceAll(value, `\`, `\\`), `"`, `\"`)
}
