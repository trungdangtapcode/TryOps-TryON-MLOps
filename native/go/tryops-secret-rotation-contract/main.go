package main

import (
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	report, err := evaluate(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "secret rotation contract failed: %v\n", err)
		os.Exit(1)
	}
	if err := writeJSON(joinRoot(cfg.RootPath, cfg.OutputPath), report); err != nil {
		fmt.Fprintf(os.Stderr, "write secret rotation report: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s passed=%t production_ready=%t checks=%d/%d\n", cfg.OutputPath, report.Passed, report.ProductionReady, report.Summary.PassedChecks, report.Summary.TotalChecks)
	if !report.Passed {
		os.Exit(1)
	}
}
