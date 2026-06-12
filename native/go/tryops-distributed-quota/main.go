package main

import (
	"context"
	"fmt"
	"os"
	"time"
)

func main() {
	cfg, err := parseConfig(os.Args[1:])
	if err != nil {
		fmt.Fprintf(os.Stderr, "config: %v\n", err)
		os.Exit(2)
	}
	ctx := context.Background()
	attempts := runDistributedQuota(ctx, cfg)
	report := buildReport(cfg, attempts, time.Now())
	if err := writeReport(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(2)
	}
	if !report.Passed {
		fmt.Fprintf(os.Stderr, "distributed quota admission failed: allowed=%d expected=%d errors=%d\n", report.Summary.Allowed, report.Summary.ExpectedAllow, report.Summary.Errors)
		os.Exit(1)
	}
}
