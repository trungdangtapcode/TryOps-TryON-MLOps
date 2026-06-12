package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestMissingSubstrings(t *testing.T) {
	missing := missingSubstrings("TryOps Console ready", []string{"TryOps", "missing"})
	if len(missing) != 1 || missing[0] != "missing" {
		t.Fatalf("unexpected missing list: %#v", missing)
	}
}

func TestRunCheckPassesWithExpectedBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	}))
	defer server.Close()

	result := runCheck(
		context.Background(),
		&http.Client{Timeout: time.Second},
		smokeCheck{
			Name:         "health",
			Method:       http.MethodGet,
			URL:          server.URL,
			WantStatus:   http.StatusOK,
			WantContains: []string{`"status":"ok"`},
		},
		1,
	)
	if !result.Passed {
		t.Fatalf("expected pass: %#v", result)
	}
}
