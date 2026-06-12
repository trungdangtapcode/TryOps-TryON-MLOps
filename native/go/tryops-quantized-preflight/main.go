package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	ctx, cancel := context.WithTimeout(context.Background(), cfg.Timeout)
	defer cancel()
	report := runPreflight(ctx, cfg)
	printSummary(report)
	if err := writeReport(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(2)
	}
	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if report.Status == "failed" {
		os.Exit(1)
	}
}
