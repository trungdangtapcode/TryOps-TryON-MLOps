package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	report, err := buildReport(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := writeReport(cfg.Output, report); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	body, _ := json.MarshalIndent(report, "", "  ")
	fmt.Println(string(body))
	if !report.Passed {
		os.Exit(2)
	}
}
