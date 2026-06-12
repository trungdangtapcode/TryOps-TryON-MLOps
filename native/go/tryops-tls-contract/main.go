package main

import (
	"context"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	if cfg.Mode != "plan" && cfg.Mode != "live" {
		fmt.Fprintf(os.Stderr, "unsupported mode %q; expected plan or live\n", cfg.Mode)
		os.Exit(2)
	}
	report := evaluate(context.Background(), cfg)
	if err := writeReport(cfg.OutputPath, report); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	body, err := os.ReadFile(cfg.OutputPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Print(string(body))
	if !report.Passed {
		os.Exit(1)
	}
}
