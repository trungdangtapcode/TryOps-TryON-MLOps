package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

func writeReport(path string, report Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}

func printSummary(report Report) {
	fmt.Printf("quantized_preflight status=%s passed=%v suitable=%d/%d load_ready=%d/%d gptq=%s awq=%s\n",
		report.Status,
		report.Passed,
		report.Summary.SuitableCandidates,
		report.Summary.TotalCandidates,
		report.Summary.LoadReadyCandidates,
		report.Summary.TotalCandidates,
		report.Summary.GPTQStatus,
		report.Summary.AWQStatus,
	)
}
