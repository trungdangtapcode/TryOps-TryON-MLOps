package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	benchmark, err := readBenchmark(cfg.InputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read benchmark: %v\n", err)
		os.Exit(2)
	}
	policy, err := readPolicy(cfg.PolicyPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read policy: %v\n", err)
		os.Exit(2)
	}
	rules := evaluateGate(benchmark, policy)
	report := buildReport(cfg, benchmark, policy, rules)
	printReport(report)
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
