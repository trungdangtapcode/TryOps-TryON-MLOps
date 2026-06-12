package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	compose, err := loadCompose(cfg.ComposePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load compose: %v\n", err)
		os.Exit(2)
	}
	report := evaluateContracts(cfg, compose)
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
