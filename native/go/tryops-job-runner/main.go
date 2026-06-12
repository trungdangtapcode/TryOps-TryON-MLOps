package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

func main() {
	cfg := parseConfig()
	if err := ensureDemoAssets(cfg); err != nil {
		fmt.Fprintf(os.Stderr, "prepare demo assets: %v\n", err)
		os.Exit(2)
	}
	ctx, cancel := context.WithTimeout(context.Background(), cfg.TotalTimeout)
	defer cancel()

	client := &http.Client{Timeout: cfg.JobTimeout + 5*time.Second}
	results := runJobs(ctx, client, cfg, buildJobSpecs(cfg))
	report := buildReport(cfg, results)
	printSummary(report)
	if err := writeReport(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(2)
	}
	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if !report.Passed {
		os.Exit(1)
	}
}
