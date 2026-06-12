package main

import (
	"flag"
	"os"
)

type Config struct {
	Root               string
	BenchmarkPath      string
	SLOGatePath        string
	PerfStatsPath      string
	ConfigContractPath string
	OutputPath         string
	MarkdownPath       string
	StepSummaryPath    string
	ArtifactName       string
}

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.Root, "root", ".", "repository root")
	flag.StringVar(&cfg.BenchmarkPath, "benchmark", "artifacts/eval/gateway_benchmark/native_gateway_benchmark.json", "native gateway benchmark report")
	flag.StringVar(&cfg.SLOGatePath, "slo-gate", "artifacts/eval/slo/native_slo_gate_report.json", "native SLO gate report")
	flag.StringVar(&cfg.PerfStatsPath, "perf-stats", "artifacts/eval/perf_stats/perf_stats.json", "native C++ perf stats report")
	flag.StringVar(&cfg.ConfigContractPath, "config-contract", "artifacts/eval/config/native_config_contract_report.json", "native config contract report")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/performance/native_performance_budget.json", "JSON report output path")
	flag.StringVar(&cfg.MarkdownPath, "markdown-output", "artifacts/eval/performance/native_performance_budget.md", "Markdown report output path")
	flag.StringVar(&cfg.StepSummaryPath, "step-summary", os.Getenv("GITHUB_STEP_SUMMARY"), "optional GitHub Actions step summary path")
	flag.StringVar(&cfg.ArtifactName, "artifact-name", "tryops-native-performance-budget", "recommended CI artifact name")
	flag.Parse()
	return cfg
}
