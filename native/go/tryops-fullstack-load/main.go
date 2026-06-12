package main

import (
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	report, err := RunFullStackLoad(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "native full-stack load failed: %v\n", err)
		os.Exit(1)
	}
	if err := WriteReport(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write native full-stack load report: %v\n", err)
		os.Exit(1)
	}
	PrintSummary(report)
	if !report.Passed {
		os.Exit(2)
	}
}
