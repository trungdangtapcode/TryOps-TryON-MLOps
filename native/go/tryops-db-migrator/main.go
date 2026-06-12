package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"
)

func main() {
	cfg := parseConfig()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	report, err := buildReport(ctx, cfg)
	if writeErr := writeReport(cfg.OutputPath, report); writeErr != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", writeErr)
		os.Exit(2)
	}
	body, _ := json.Marshal(report)
	fmt.Println(string(body))
	if err != nil {
		fmt.Fprintf(os.Stderr, "migration error: %v\n", err)
		os.Exit(1)
	}
	if !report.Passed {
		os.Exit(1)
	}
}
