package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

func buildReport(tools []toolStatus, scans []scanResult) vulnerabilityReport {
	passed := len(scans) > 0
	for _, scan := range scans {
		if !scan.Passed {
			passed = false
			break
		}
	}
	missing := missingRequiredTools(tools)
	coverage := "partial"
	if len(missing) == 0 {
		coverage = "enterprise"
	}
	return vulnerabilityReport{
		SchemaVersion:        "tryops.vulnerability_scan.v1",
		GeneratedAt:          time.Now().UTC().Format(time.RFC3339),
		Passed:               passed,
		CoverageLevel:        coverage,
		ProductionReady:      passed && len(missing) == 0,
		MissingRequiredTools: missing,
		Tools:                tools,
		Scans:                scans,
		Notes: []string{
			"Missing production scanners are recorded as coverage gaps, not hidden as passes.",
			"Current local evidence is limited to scanners installed in this workspace.",
		},
	}
}

func writeReport(path string, report vulnerabilityReport) error {
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

func relativePath(root string, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return path
	}
	return rel
}
