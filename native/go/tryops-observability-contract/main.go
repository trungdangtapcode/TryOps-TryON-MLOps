package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	report, err := evaluate(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if err := writeReport(resolve(cfg.Root, cfg.OutputPath), report); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	payload, _ := json.MarshalIndent(report, "", "  ")
	fmt.Println(string(payload))
	if !report.Passed {
		os.Exit(1)
	}
}
