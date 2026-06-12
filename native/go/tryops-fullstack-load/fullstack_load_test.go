package main

import (
	"net/http"
	"testing"
)

func TestWeightedRequests(t *testing.T) {
	if got := weightedRequests(12, 3); got != 36 {
		t.Fatalf("expected weighted requests, got %d", got)
	}
	if got := weightedRequests(0, 0); got != 1 {
		t.Fatalf("expected minimum request count, got %d", got)
	}
}

func TestEvaluateSLOFailsOnLatencyAndErrors(t *testing.T) {
	cfg := Config{MaxErrorRate: 0, DefaultMaxP95MS: 10, DefaultMaxP99MS: 20, DefaultMinRPS: 5}
	result := LoadResult{
		Requests:       10,
		Errors:         1,
		ErrorRate:      0.1,
		RequestsPerSec: 3,
		LatencyMs:      LatencySummary{P95: 11, P99: 21},
	}
	slo := evaluateSLO(result, HTTPRequestSpec{Name: "demo"}, cfg)
	if slo.Passed || len(slo.Failures) != 4 {
		t.Fatalf("expected 4 SLO failures, got %#v", slo)
	}
}

func TestBuildScenariosCoversProductPaths(t *testing.T) {
	scenarios := buildScenarios("http://127.0.0.1:8081", Config{DefaultMaxP95MS: 1000, DefaultMaxP99MS: 2000, DefaultMinRPS: 1})
	names := map[string]bool{}
	for _, scenario := range scenarios {
		names[scenario.Name] = true
		if scenario.ExpectedStatus != http.StatusOK {
			t.Fatalf("scenario %s has unexpected status %d", scenario.Name, scenario.ExpectedStatus)
		}
	}
	for _, required := range []string{"gateway_health", "rbac_session_viewer", "evaluation_summary", "quota_summary", "llm_generate", "promotion_gate_operator"} {
		if !names[required] {
			t.Fatalf("missing scenario %s", required)
		}
	}
}

func TestExternalGateHonorsRequiredTools(t *testing.T) {
	tools := []ExternalTool{{Name: "k6", Required: true, Available: false}, {Name: "locust", Required: true, Available: false}}
	if externalAvailable(tools) {
		t.Fatal("expected missing external tools to be unavailable")
	}
	if externalGatePassed(tools) {
		t.Fatal("expected required missing external tools to fail readiness")
	}
	tools[0].Available = true
	if !externalGatePassed(tools) {
		t.Fatal("expected one external tool to satisfy readiness")
	}
}
