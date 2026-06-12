package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	input, err := loadQuotaUsage(cfg.InputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load quota input: %v\n", err)
		os.Exit(2)
	}
	report := buildReadModel(input, cfg.InputPath)
	if err := writeJSON(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write quota read model: %v\n", err)
		os.Exit(2)
	}
	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if !report.Passed {
		os.Exit(1)
	}
}
