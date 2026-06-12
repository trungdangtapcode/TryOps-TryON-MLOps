package main

import (
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	report, err := evaluate(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ci contract: %v\n", err)
		os.Exit(1)
	}
	if err := writeJSON(rootJoin(cfg.RootPath, cfg.OutputPath), report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("ci contract: passed=%t production_ready=%t checks=%d missing_tools=%d\n", report.Passed, report.ProductionReady, len(report.Checks), len(report.MissingRequiredTools))
	if !report.Passed {
		os.Exit(1)
	}
}
