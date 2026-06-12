package main

import (
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	cfg := parseConfig()
	report, prometheus, err := buildReport(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	outputPath := filepath.Join(cfg.Root, cfg.OutputPath)
	prometheusPath := filepath.Join(cfg.Root, cfg.PrometheusPath)
	if err := writeJSON(outputPath, report); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if err := writePrometheus(prometheusPath, prometheus); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	fmt.Println(prometheus)
	if !report.Passed {
		os.Exit(1)
	}
}
