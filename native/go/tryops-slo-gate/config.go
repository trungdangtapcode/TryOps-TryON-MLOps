package main

import (
	"flag"
	"os"
	"strings"
)

type config struct {
	InputPath  string
	PolicyPath string
	OutputPath string
}

func parseConfig() config {
	cfg := config{}
	flag.StringVar(&cfg.InputPath, "input", getenv("TRYOPS_SLO_GATE_INPUT", "artifacts/eval/gateway_benchmark/native_gateway_benchmark.json"), "native benchmark input report")
	flag.StringVar(&cfg.PolicyPath, "policy", getenv("TRYOPS_SLO_GATE_POLICY", ""), "optional JSON policy override")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_SLO_GATE_OUTPUT", "artifacts/eval/slo/native_slo_gate_report.json"), "JSON gate report output")
	flag.Parse()
	return cfg
}

func getenv(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}
