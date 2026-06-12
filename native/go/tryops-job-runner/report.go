package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func buildReport(cfg config, results []jobResult) jobReport {
	passed := true
	passedCount := 0
	for _, result := range results {
		if result.Passed {
			passedCount++
		} else {
			passed = false
		}
	}
	return jobReport{
		SchemaVersion: "tryops.native_job_runner.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		BaseURL:       cfg.BaseURL,
		Passed:        passed,
		Summary: reportSummary{
			Total:  len(results),
			Passed: passedCount,
			Failed: len(results) - passedCount,
		},
		Config: map[string]interface{}{
			"job_timeout_ms":   cfg.JobTimeout.Milliseconds(),
			"poll_timeout_ms":  cfg.PollTimeout.Milliseconds(),
			"retry_attempts":   cfg.RetryAttempts,
			"quota_plan":       cfg.QuotaPlan,
			"person_image":     cfg.PersonImagePath,
			"garment_image":    cfg.GarmentImagePath,
			"vton_output_path": cfg.VTONOutputPath,
		},
		Jobs: results,
	}
}

func writeReport(path string, report jobReport) error {
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

func printSummary(report jobReport) {
	for _, result := range report.Jobs {
		status := "FAIL"
		if result.Passed {
			status = "PASS"
		}
		fmt.Printf("%s %s attempts=%d polls=%d duration_ms=%d\n", status, result.Name, result.Attempts, result.Polls, result.DurationMS)
	}
}
