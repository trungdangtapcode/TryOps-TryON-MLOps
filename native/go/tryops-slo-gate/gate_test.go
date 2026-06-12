package main

import "testing"

func TestEvaluateGatePassesNativeBenchmark(t *testing.T) {
	report := fixtureBenchmark()
	results := evaluateGate(report, defaultPolicy())
	gate := buildReport(config{InputPath: "fixture.json"}, report, defaultPolicy(), results)
	if !gate.Passed {
		t.Fatalf("expected pass, got %#v", gate.Rules)
	}
	if gate.Summary.TotalRules != 3 || gate.Summary.FailedRules != 0 {
		t.Fatalf("unexpected summary %#v", gate.Summary)
	}
}

func TestEvaluateGateFailsLatencyRegression(t *testing.T) {
	report := fixtureBenchmark()
	load := report.Scenarios["promotion_post_edge_proxy"].Results["native_rust_gateway_proxy_to_fastapi"]
	load.LatencyMs.P95 = 250
	report.Scenarios["promotion_post_edge_proxy"].Results["native_rust_gateway_proxy_to_fastapi"] = load
	results := evaluateGate(report, defaultPolicy())
	gate := buildReport(config{InputPath: "fixture.json"}, report, defaultPolicy(), results)
	if gate.Passed {
		t.Fatalf("expected gate failure")
	}
	found := false
	for _, rule := range gate.Rules {
		for _, failure := range rule.Failures {
			if failure == "p95_ms 250.000 > 150.000" {
				found = true
			}
		}
	}
	if !found {
		t.Fatalf("expected p95 failure, got %#v", gate.Rules)
	}
}

func TestEvaluateGateFailsMissingScenario(t *testing.T) {
	report := fixtureBenchmark()
	delete(report.Scenarios, "health_get")
	results := evaluateGate(report, defaultPolicy())
	if results[0].Passed {
		t.Fatalf("expected missing scenario failure")
	}
}

func fixtureBenchmark() BenchmarkReport {
	return BenchmarkReport{
		SchemaVersion: "tryops.native_gateway_benchmark.v1",
		CreatedAt:     "2026-06-11T00:00:00Z",
		Scenarios: map[string]ScenarioReport{
			"health_get": {
				Endpoint: "/health",
				Results: map[string]LoadResult{
					"native_rust_gateway": {
						Requests:       12000,
						Errors:         0,
						RequestsPerSec: 24000,
						LatencyMs:      LatencySummary{P95: 6, P99: 11},
					},
					"python_fastapi": {
						Requests:       12000,
						Errors:         0,
						RequestsPerSec: 1500,
						LatencyMs:      LatencySummary{P95: 60, P99: 75},
					},
				},
			},
			"promotion_post_direct": {
				Endpoint: "/v1/promotion/evaluate",
				Results: map[string]LoadResult{
					"native_rust_gateway": {
						Requests:       12000,
						Errors:         0,
						RequestsPerSec: 22000,
						LatencyMs:      LatencySummary{P95: 6, P99: 9},
					},
					"python_fastapi": {
						Requests:       12000,
						Errors:         0,
						RequestsPerSec: 750,
						LatencyMs:      LatencySummary{P95: 96, P99: 120},
					},
				},
			},
			"promotion_post_edge_proxy": {
				Endpoint: "/api/promotion/evaluate -> /v1/promotion/evaluate",
				Results: map[string]LoadResult{
					"native_rust_gateway_proxy_to_fastapi": {
						Requests:       12000,
						Errors:         0,
						RequestsPerSec: 700,
						LatencyMs:      LatencySummary{P95: 105, P99: 135},
					},
					"python_fastapi_direct": {
						Requests:       12000,
						Errors:         0,
						RequestsPerSec: 760,
						LatencyMs:      LatencySummary{P95: 96, P99: 120},
					},
				},
			},
		},
	}
}
