package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestRunProbeAgainstOpenAICompatibleServer(t *testing.T) {
	var chatRequests int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/v1/models":
			writeJSON(w, map[string]interface{}{
				"object": "list",
				"data": []map[string]string{
					{"id": "test-model", "object": "model"},
				},
			})
		case "/v1/chat/completions":
			chatRequests++
			writeJSON(w, map[string]interface{}{
				"id":      fmt.Sprintf("chatcmpl-%d", chatRequests),
				"object":  "chat.completion",
				"choices": []map[string]interface{}{{"message": map[string]string{"role": "assistant", "content": "native probe ok"}}},
				"usage":   map[string]int{"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
			})
		case "/metrics":
			w.Header().Set("Content-Type", "text/plain")
			fmt.Fprintln(w, "vllm:request_success_total 4")
			fmt.Fprintln(w, "vllm:num_requests_running 0")
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	cfg := Config{
		BaseURL:        server.URL + "/v1",
		MetricsURL:     server.URL + "/metrics",
		Model:          "test-model",
		Prompt:         "hello",
		Requests:       3,
		Concurrency:    2,
		MaxTokens:      8,
		RequestTimeout: 2 * time.Second,
		TotalTimeout:   5 * time.Second,
	}
	report := runProbe(context.Background(), cfg)
	if !report.Passed || report.Status != "passed" {
		t.Fatalf("expected passed report, got status=%s reasons=%v", report.Status, report.Reasons)
	}
	if report.Models.Selected != "test-model" {
		t.Fatalf("unexpected selected model %q", report.Models.Selected)
	}
	if report.Load.Succeeded != 3 || report.Load.Failed != 0 {
		t.Fatalf("unexpected load result: %+v", report.Load)
	}
	if !report.Metrics.ContainsVLLMMetrics {
		t.Fatalf("expected vLLM metrics marker")
	}
}

func TestRunProbeSkippedWhenEndpointIsDown(t *testing.T) {
	cfg := Config{
		BaseURL:        "http://127.0.0.1:1/v1",
		MetricsURL:     "http://127.0.0.1:1/metrics",
		Model:          "test-model",
		Prompt:         "hello",
		Requests:       1,
		Concurrency:    1,
		MaxTokens:      8,
		RequestTimeout: 100 * time.Millisecond,
		TotalTimeout:   time.Second,
	}
	report := runProbe(context.Background(), cfg)
	if report.Status != "skipped" || report.Passed {
		t.Fatalf("expected skipped false report, got status=%s passed=%v", report.Status, report.Passed)
	}
	if len(report.Reasons) == 0 {
		t.Fatalf("expected a skip reason")
	}
}

func TestMetricsURLForBase(t *testing.T) {
	got := metricsURLForBase("http://localhost:8000/v1")
	if got != "http://localhost:8000/metrics" {
		t.Fatalf("unexpected metrics URL: %s", got)
	}
}

func writeJSON(w http.ResponseWriter, value map[string]interface{}) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(value)
}
