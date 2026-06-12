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
	client := &http.Client{Timeout: 5 * time.Second}
	results := make([]checkResult, 0)
	for _, check := range buildChecks(cfg) {
		ctx, cancel := context.WithTimeout(context.Background(), cfg.Timeout)
		result := runCheck(ctx, client, check, cfg.Retries)
		cancel()
		results = append(results, result)
		status := "PASS"
		if !result.Passed {
			status = "FAIL"
		}
		fmt.Printf("%s %s attempts=%d duration_ms=%d\n", status, result.Name, result.Attempts, result.DurationMS)
	}

	report := buildReport(results)
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
