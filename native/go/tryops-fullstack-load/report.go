package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

func WriteReport(path string, report Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	payload = append(payload, '\n')
	return os.WriteFile(path, payload, 0o644)
}

func PrintSummary(report Report) {
	fmt.Printf(
		"fullstack load: passed=%v scenarios=%d/%d requests=%d errors=%d worst_p95=%.2fms worst_p99=%.2fms\n",
		report.Passed,
		report.Summary.PassedScenarios,
		report.Summary.TotalScenarios,
		report.Summary.TotalRequests,
		report.Summary.TotalErrors,
		report.Summary.WorstP95MS,
		report.Summary.WorstP99MS,
	)
	for _, scenario := range report.Scenarios {
		fmt.Printf(
			"  %-24s %7.2f rps p95=%8.3fms p99=%8.3fms errors=%d pass=%v\n",
			scenario.Name,
			scenario.Load.RequestsPerSec,
			scenario.Load.LatencyMs.P95,
			scenario.Load.LatencyMs.P99,
			scenario.Load.Errors,
			scenario.SLO.Passed,
		)
	}
}
