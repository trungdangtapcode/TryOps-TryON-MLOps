package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	envelopes, source, err := loadEnvelopes(cfg.InputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load envelopes: %v\n", err)
		os.Exit(2)
	}
	report := buildReport(envelopes, source)
	if err := writeJSON(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(2)
	}
	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if !report.Passed {
		os.Exit(1)
	}
}
