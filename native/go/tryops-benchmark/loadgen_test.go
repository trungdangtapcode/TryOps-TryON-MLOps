package main

import "testing"

func TestSummarizeComputesThroughputAndPercentiles(t *testing.T) {
	result := summarize([]float64{4, 1, 2, 3}, 0.5, 0, 4)

	if result.Requests != 4 {
		t.Fatalf("requests = %d, want 4", result.Requests)
	}
	if result.RequestsPerSec != 8 {
		t.Fatalf("requests_per_sec = %v, want 8", result.RequestsPerSec)
	}
	if result.LatencyMs.P50 != 3 {
		t.Fatalf("p50 = %v, want 3", result.LatencyMs.P50)
	}
	if result.LatencyMs.P99 != 4 {
		t.Fatalf("p99 = %v, want 4", result.LatencyMs.P99)
	}
}

func TestSpeedupUsesNativeOverPythonThroughputAndLatency(t *testing.T) {
	native := LoadResult{
		RequestsPerSec: 4000,
		LatencyMs:      LatencySummary{P50: 5, P99: 20},
	}
	python := LoadResult{
		RequestsPerSec: 1000,
		LatencyMs:      LatencySummary{P50: 25, P99: 60},
	}

	got := speedup(native, python)
	if got == nil {
		t.Fatal("expected speedup report")
	}
	if got.ThroughputX != 4 || got.P50LatencyX != 5 || got.P99LatencyX != 3 {
		t.Fatalf("unexpected speedup: %+v", got)
	}
}
