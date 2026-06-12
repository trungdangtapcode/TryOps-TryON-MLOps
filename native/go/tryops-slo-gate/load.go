package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func readBenchmark(path string) (BenchmarkReport, error) {
	payload, err := os.ReadFile(path)
	if err != nil {
		return BenchmarkReport{}, err
	}
	var report BenchmarkReport
	if err := json.Unmarshal(payload, &report); err != nil {
		return BenchmarkReport{}, err
	}
	if report.SchemaVersion != "tryops.native_gateway_benchmark.v1" {
		return BenchmarkReport{}, fmt.Errorf("unsupported benchmark schema %q", report.SchemaVersion)
	}
	if len(report.Scenarios) == 0 {
		return BenchmarkReport{}, fmt.Errorf("benchmark report has no scenarios")
	}
	return report, nil
}

func readPolicy(path string) (GatePolicy, error) {
	if path == "" {
		return defaultPolicy(), nil
	}
	payload, err := os.ReadFile(path)
	if err != nil {
		return GatePolicy{}, err
	}
	var policy GatePolicy
	if err := json.Unmarshal(payload, &policy); err != nil {
		return GatePolicy{}, err
	}
	if len(policy.Rules) == 0 {
		return GatePolicy{}, fmt.Errorf("policy has no rules")
	}
	return policy, nil
}
