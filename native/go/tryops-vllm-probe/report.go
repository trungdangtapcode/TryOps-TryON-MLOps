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
	fmt.Printf("vllm_probe status=%s passed=%v endpoint=%s model=%s\n", report.Status, report.Passed, report.Target.BaseURL, report.Target.Model)
	if len(report.Reasons) > 0 {
		fmt.Printf("reason=%s\n", report.Reasons[0])
	}
}
