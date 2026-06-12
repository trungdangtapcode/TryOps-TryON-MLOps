package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

func buildReport(commands []commandResult, evidence []evidenceResult) acceptanceReport {
	passed := true
	passedChecks := 0
	failedChecks := 0
	for _, result := range commands {
		if result.Passed {
			passedChecks++
		} else {
			passed = false
			failedChecks++
		}
	}
	for _, result := range evidence {
		if result.Passed {
			passedChecks++
		} else {
			passed = false
			failedChecks++
		}
	}
	return acceptanceReport{
		SchemaVersion: "tryops.professor_demo_acceptance.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		Summary: reportSummary{
			CommandChecks:  len(commands),
			EvidenceChecks: len(evidence),
			PassedChecks:   passedChecks,
			FailedChecks:   failedChecks,
		},
		Commands: commands,
		Evidence: evidence,
	}
}

func writeReport(path string, report acceptanceReport) error {
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
