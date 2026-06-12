package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	ctx, cancel := context.WithTimeout(context.Background(), cfg.TotalTimeout)
	defer cancel()
	report := runProbe(ctx, cfg)
	printSummary(report)
	if err := writeReport(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(2)
	}
	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if cfg.RequireLive && !report.Passed {
		os.Exit(1)
	}
}
