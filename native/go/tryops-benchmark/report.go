package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

func WriteReport(path string, report BenchmarkReport) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	payload = append(payload, '\n')
	return os.WriteFile(path, payload, 0o644)
}

func PrintSummary(report BenchmarkReport) {
	for name, scenario := range report.Scenarios {
		fmt.Printf("%s (%s)\n", name, scenario.Endpoint)
		for target, result := range scenario.Results {
			fmt.Printf(
				"  %-36s %9.0f req/s  p50=%7.3fms p99=%7.3fms errors=%d\n",
				target,
				result.RequestsPerSec,
				result.LatencyMs.P50,
				result.LatencyMs.P99,
				result.Errors,
			)
		}
		if scenario.Speedup != nil {
			fmt.Printf(
				"  native comparison: %.2fx throughput, %.2fx lower p50, %.2fx lower p99\n",
				scenario.Speedup.ThroughputX,
				scenario.Speedup.P50LatencyX,
				scenario.Speedup.P99LatencyX,
			)
		}
	}
}
