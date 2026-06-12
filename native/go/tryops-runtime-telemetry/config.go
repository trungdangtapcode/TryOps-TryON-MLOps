package main

import "flag"

type Config struct {
	Root            string
	BenchmarkPath   string
	ParetoPath      string
	OutputPath      string
	PrometheusPath  string
	NvidiaSMIBinary string
}

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.Root, "root", ".", "repository root")
	flag.StringVar(&cfg.BenchmarkPath, "benchmark", "artifacts/eval/llm_baseline/benchmark.json", "LLM benchmark artifact")
	flag.StringVar(&cfg.ParetoPath, "pareto", "artifacts/eval/llm_pareto/pareto.json", "LLM Pareto artifact")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/runtime/native_runtime_telemetry.json", "JSON report output")
	flag.StringVar(&cfg.PrometheusPath, "prometheus-output", "artifacts/eval/runtime/native_runtime_telemetry.prom", "Prometheus text output")
	flag.StringVar(&cfg.NvidiaSMIBinary, "nvidia-smi", "nvidia-smi", "nvidia-smi binary path")
	flag.Parse()
	return cfg
}
