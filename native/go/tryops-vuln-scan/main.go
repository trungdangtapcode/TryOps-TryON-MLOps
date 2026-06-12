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

	tools := discoverTools()
	scans := make([]scanResult, 0)
	if toolAvailable(tools, "npm") {
		scans = append(scans, runNPMAudit(ctx, cfg))
	}

	for _, scan := range scans {
		status := "PASS"
		if !scan.Passed {
			status = "FAIL"
		}
		fmt.Printf("%s %s tool=%s path=%s\n", status, scan.Name, scan.Tool, scan.Path)
	}

	report := buildReport(tools, scans)
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
