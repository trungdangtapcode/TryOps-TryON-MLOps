package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestDispatchEventsWritesAuditAndSignedWebhook(t *testing.T) {
	secret := "test-secret"
	received := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if !verifySignature(secret, r.Header.Get("X-TryOps-Webhook-Timestamp"), body, r.Header.Get("X-TryOps-Signature-256")) {
			t.Fatalf("invalid signature")
		}
		var event Event
		if err := json.Unmarshal(body, &event); err != nil {
			t.Fatalf("decode event: %v", err)
		}
		received++
		w.WriteHeader(http.StatusAccepted)
	}))
	defer server.Close()

	tmp := t.TempDir()
	cfg := config{
		AuditLogPath:  filepath.Join(tmp, "audit.jsonl"),
		WebhookURL:    server.URL,
		WebhookSecret: secret,
		Retries:       2,
		RetryDelay:    time.Millisecond,
	}
	results, err := dispatchEvents(context.Background(), server.Client(), cfg, sampleEvents())
	if err != nil {
		t.Fatalf("dispatch: %v", err)
	}
	report := buildReport("test", receiverSummary{Enabled: true, AcceptedEvents: received}, results)
	if !report.Passed {
		t.Fatalf("expected pass: %#v", report)
	}
	if received != len(sampleEvents()) {
		t.Fatalf("received %d events", received)
	}
	lines, err := os.ReadFile(cfg.AuditLogPath)
	if err != nil {
		t.Fatalf("read audit: %v", err)
	}
	if countLines(string(lines)) != len(sampleEvents()) {
		t.Fatalf("unexpected audit log: %s", string(lines))
	}
}

func TestDispatchRetriesWebhook(t *testing.T) {
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts == 1 {
			http.Error(w, "temporary", http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	defer server.Close()

	cfg := config{
		AuditLogPath:  filepath.Join(t.TempDir(), "audit.jsonl"),
		WebhookURL:    server.URL,
		WebhookSecret: "test-secret",
		Retries:       2,
		RetryDelay:    time.Millisecond,
	}
	results, err := dispatchEvents(context.Background(), server.Client(), cfg, sampleEvents()[:1])
	if err != nil {
		t.Fatalf("dispatch: %v", err)
	}
	if !results[0].WebhookSent || results[0].Attempts != 2 {
		t.Fatalf("expected retry success, got %#v", results[0])
	}
}

func TestValidateEventsRejectsDuplicateID(t *testing.T) {
	events := sampleEvents()[:2]
	events[1].ID = events[0].ID
	if err := validateEvents(events); err == nil {
		t.Fatalf("expected duplicate id failure")
	}
}

func countLines(value string) int {
	count := 0
	for _, ch := range value {
		if ch == '\n' {
			count++
		}
	}
	return count
}
