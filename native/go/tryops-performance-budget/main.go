package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	artifacts, err := loadArtifacts(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load artifacts: %v\n", err)
		os.Exit(2)
	}
	report := buildPerformanceBudgetReport(cfg, artifacts)
	markdown := renderMarkdown(report)
	if err := writeJSON(resolvePath(cfg.Root, cfg.OutputPath), report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(2)
	}
	if err := writeMarkdown(resolvePath(cfg.Root, cfg.MarkdownPath), markdown); err != nil {
		fmt.Fprintf(os.Stderr, "write markdown: %v\n", err)
		os.Exit(2)
	}
	if cfg.StepSummaryPath != "" {
		if err := writeMarkdown(cfg.StepSummaryPath, markdown); err != nil {
			fmt.Fprintf(os.Stderr, "write step summary: %v\n", err)
			os.Exit(2)
		}
	}
	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if !report.Passed {
		os.Exit(1)
	}
}
