package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

func buildReport(results []checkResult) smokeReport {
	passed := true
	for _, result := range results {
		if !result.Passed {
			passed = false
			break
		}
	}
	return smokeReport{
		SchemaVersion: "tryops.full_stack_smoke.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		Checks:        results,
	}
}

func writeReport(path string, report smokeReport) error {
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
