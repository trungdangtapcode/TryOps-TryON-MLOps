package main

import (
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	report := evaluate(cfg)
	if err := writeReport(rootJoin(cfg.RootPath, cfg.OutputPath), report); err != nil {
		fmt.Fprintf(os.Stderr, "write live supply-chain report: %v\n", err)
		os.Exit(2)
	}
	fmt.Printf("live supply chain: passed=%t production_ready=%t syft_packages=%d trivy_high_critical=%d cosign_verified=%t\n",
		report.Passed,
		report.ProductionReady,
		report.Syft.PackageCount,
		report.Trivy.TotalHighCritical,
		report.Cosign.Verified,
	)
	if !report.Passed {
		os.Exit(1)
	}
}
