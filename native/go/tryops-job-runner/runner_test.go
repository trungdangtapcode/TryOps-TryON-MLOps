package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestRunnerRetriesTransientHTTP(t *testing.T) {
	var mu sync.Mutex
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/llm/generate" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		mu.Lock()
		attempts++
		current := attempts
		mu.Unlock()
		if current == 1 {
			http.Error(w, `{"error":"temporary"}`, http.StatusServiceUnavailable)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"schema_version": "tryops.llm_generation.v1",
			"request_id":     "req-test-llm",
			"status":         "completed",
		})
	}))
	defer server.Close()

	cfg := testConfig(server.URL)
	spec := jobSpec{
		Name:        "llm_retry",
		Workload:    "llm",
		Method:      http.MethodPost,
		Path:        "/api/llm/generate",
		Payload:     map[string]interface{}{"request_id": "req-test-llm", "prompt": "hello"},
		Timeout:     time.Second,
		MaxAttempts: 3,
		Retry:       retryPolicy{BaseDelay: time.Millisecond},
	}
	results := runJobs(context.Background(), server.Client(), cfg, []jobSpec{spec})
	if len(results) != 1 {
		t.Fatalf("expected one result, got %d", len(results))
	}
	if !results[0].Passed {
		t.Fatalf("expected pass, got error %q", results[0].Error)
	}
	if results[0].Attempts != 2 {
		t.Fatalf("expected 2 attempts, got %d", results[0].Attempts)
	}
}

func TestRunnerPollsAsyncVTONJob(t *testing.T) {
	var mu sync.Mutex
	polls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/vton/jobs":
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"schema_version": "tryops.job.v1",
				"job_id":         "job-1",
				"status":         "accepted",
				"workload":       "vton",
			})
		case "/api/vton/jobs/job-1":
			mu.Lock()
			polls++
			current := polls
			mu.Unlock()
			status := "running"
			if current >= 2 {
				status = "completed"
			}
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"schema_version": "tryops.job.v1",
				"job_id":         "job-1",
				"status":         status,
				"workload":       "vton",
				"result": map[string]interface{}{
					"status": "completed",
				},
			})
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	cfg := testConfig(server.URL)
	spec := jobSpec{
		Name:        "vton_async",
		Workload:    "vton",
		Method:      http.MethodPost,
		Path:        "/api/vton/jobs",
		Payload:     map[string]interface{}{"request_id": "req-test-vton"},
		Timeout:     time.Second,
		MaxAttempts: 1,
		Poll: &pollSpec{
			PathPrefix: "/api/vton/jobs",
			Timeout:    time.Second,
			Interval:   time.Millisecond,
		},
	}
	result := runJob(context.Background(), server.Client(), cfg, spec)
	if !result.Passed {
		t.Fatalf("expected pass, got error %q", result.Error)
	}
	if result.JobID != "job-1" {
		t.Fatalf("expected job-1, got %q", result.JobID)
	}
	if result.Polls < 2 {
		t.Fatalf("expected at least 2 polls, got %d", result.Polls)
	}
}

func TestRunnerHonorsContextDeadline(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(150 * time.Millisecond)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "completed"})
	}))
	defer server.Close()

	cfg := testConfig(server.URL)
	spec := jobSpec{
		Name:        "deadline",
		Workload:    "llm",
		Method:      http.MethodPost,
		Path:        "/api/llm/generate",
		Payload:     map[string]interface{}{"request_id": "req-timeout"},
		Timeout:     10 * time.Millisecond,
		MaxAttempts: 1,
	}
	result := runJob(context.Background(), server.Client(), cfg, spec)
	if result.Passed {
		t.Fatalf("expected timeout failure")
	}
	if !strings.Contains(result.Error, "deadline") && !strings.Contains(result.Error, "context canceled") {
		t.Fatalf("expected context error, got %q", result.Error)
	}
}

func testConfig(baseURL string) config {
	return config{
		BaseURL:        baseURL,
		JobTimeout:     time.Second,
		PollTimeout:    time.Second,
		PollInterval:   time.Millisecond,
		RetryAttempts:  3,
		RetryBaseDelay: time.Millisecond,
		UserID:         "test-user",
		QuotaPlan:      "enterprise",
	}
}
