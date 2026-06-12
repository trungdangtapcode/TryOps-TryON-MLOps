package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func buildReport(cfg config, benchmark BenchmarkReport, policy GatePolicy, rules []RuleResult) GateReport {
	passed := true
	passedRules := 0
	for _, rule := range rules {
		if rule.Passed {
			passedRules++
		} else {
			passed = false
		}
	}
	return GateReport{
		SchemaVersion:       "tryops.native_slo_gate.v1",
		GeneratedAt:         time.Now().UTC().Format(time.RFC3339),
		InputPath:           cfg.InputPath,
		InputSchemaVersion:  benchmark.SchemaVersion,
		InputCreatedAt:      benchmark.CreatedAt,
		Passed:              passed,
		PolicySchemaVersion: policy.SchemaVersion,
		Summary: GateSummary{
			TotalRules:  len(rules),
			PassedRules: passedRules,
			FailedRules: len(rules) - passedRules,
		},
		Rules: rules,
	}
}

func writeReport(path string, report GateReport) error {
	if path == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}

func printReport(report GateReport) {
	for _, rule := range report.Rules {
		status := "FAIL"
		if rule.Passed {
			status = "PASS"
		}
		fmt.Printf("%s %s scenario=%s target=%s\n", status, rule.Name, rule.Scenario, rule.Target)
		for _, failure := range rule.Failures {
			fmt.Printf("  %s\n", failure)
		}
	}
}
