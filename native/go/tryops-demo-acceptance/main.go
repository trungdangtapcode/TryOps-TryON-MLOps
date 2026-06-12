package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	ctx, cancel := context.WithTimeout(context.Background(), cfg.Timeout)
	defer cancel()

	commandResults := runCommands(ctx, cfg, buildCommandSpecs(cfg))
	for _, result := range commandResults {
		printStatus("command", result.Name, result.Passed)
	}

	evidenceResults := runEvidenceChecks(cfg.Root, buildEvidenceSpecs())
	evidenceResults = append(evidenceResults, runSourceChecks(cfg.Root, buildSourceSpecs())...)
	for _, result := range evidenceResults {
		printStatus("evidence", result.Name, result.Passed)
	}

	report := buildReport(commandResults, evidenceResults)
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

func printStatus(kind string, name string, passed bool) {
	status := "PASS"
	if !passed {
		status = "FAIL"
	}
	fmt.Printf("%s %s %s\n", status, kind, name)
}
