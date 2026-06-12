package main

import (
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	report, err := evaluate(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "dependency lock contract failed: %v\n", err)
		os.Exit(1)
	}
	if err := writeJSON(joinRoot(cfg.RootPath, cfg.OutputPath), report); err != nil {
		fmt.Fprintf(os.Stderr, "write dependency lock report: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s passed=%t checks=%d/%d python=%d node=%d rust=%d go_modules=%d\n", cfg.OutputPath, report.Passed, report.Summary.PassedChecks, report.Summary.TotalChecks, report.Summary.PythonLocked, report.Summary.NodeLocked, report.Summary.RustLocked, report.Summary.GoModules)
	if !report.Passed {
		os.Exit(1)
	}
}
