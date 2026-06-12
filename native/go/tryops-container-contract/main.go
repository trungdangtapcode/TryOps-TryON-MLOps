package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	manifest, err := loadManifest(cfg.Root, cfg.ManifestPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load manifest: %v\n", err)
		os.Exit(2)
	}
	compose, err := loadCompose(cfg.Root, cfg.ComposePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load compose: %v\n", err)
		os.Exit(2)
	}
	report := evaluate(cfg.Root, manifest, compose, cfg.ManifestPath, cfg.ComposePath)
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
