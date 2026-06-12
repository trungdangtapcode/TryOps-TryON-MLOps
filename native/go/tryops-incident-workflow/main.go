package main

import (
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	report, _, err := evaluateWorkflow(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "incident workflow evaluation failed: %v\n", err)
		os.Exit(1)
	}
	outputPath := joinRoot(cfg.RootPath, cfg.OutputPath)
	if err := writeJSON(outputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write incident workflow report: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s passed=%t production_ready=%t checks=%d/%d\n", cfg.OutputPath, report.Passed, report.ProductionReady, report.Summary.PassedChecks, report.Summary.TotalChecks)
	if !report.Passed {
		os.Exit(1)
	}
}
