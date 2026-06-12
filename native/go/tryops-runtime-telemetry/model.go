package main

import (
	"math"
	"path/filepath"
	"time"
)

func buildReport(cfg Config) (Report, string, error) {
	benchmarkPath := filepath.Join(cfg.Root, cfg.BenchmarkPath)
	paretoPath := filepath.Join(cfg.Root, cfg.ParetoPath)
	llm, err := loadLLMTelemetry(benchmarkPath, paretoPath)
	if err != nil {
		return Report{}, "", err
	}
	gpu := queryGPU(cfg.NvidiaSMIBinary)
	checks := map[string]bool{
		"benchmark_tokens_per_second_present": llm.Benchmark.TokensPerSecond > 0,
		"benchmark_memory_present":            llm.Benchmark.MemoryGB > 0,
		"phase_timing_present":                llm.Benchmark.PhaseTimingPresent,
		"pareto_variants_present":             llm.VariantCount > 0,
		"pareto_tokens_per_second_present":    variantsHaveTPS(llm.Variants),
		"pareto_vram_present":                 variantsHaveVRAM(llm.Variants),
		"native_slo_stats_present":            llm.NativeSLOGateCount > 0,
		"nvidia_smi_gpu_snapshot_present":     gpu.Available && len(gpu.Devices) > 0,
	}
	prometheus := renderPrometheus(llm, gpu)
	checks["prometheus_text_present"] = prometheus != ""
	passed := true
	for _, value := range checks {
		passed = passed && value
	}
	report := Report{
		SchemaVersion: "tryops.native_runtime_telemetry.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		CoverageLevel: "native_go_llm_gpu_runtime_exporter",
		Sources: Sources{
			BenchmarkPath: cfg.BenchmarkPath,
			ParetoPath:    cfg.ParetoPath,
			NvidiaSMI:     cfg.NvidiaSMIBinary,
		},
		Research: []ResearchSource{
			{
				Name: "NVIDIA nvidia-smi query interface",
				URL:  "https://docs.nvidia.com/deploy/nvidia-smi/",
				Use:  "native GPU memory, utilization, and power snapshot source",
			},
			{
				Name: "Prometheus text exposition format",
				URL:  "https://prometheus.io/docs/instrumenting/exposition_formats/",
				Use:  "portable metrics output for tokens/sec, VRAM, and GPU utilization",
			},
		},
		LLM:            llm,
		GPU:            gpu,
		PrometheusPath: cfg.PrometheusPath,
		Checks:         checks,
	}
	return report, prometheus, nil
}

func variantsHaveTPS(variants []VariantTelemetry) bool {
	for _, variant := range variants {
		if variant.Available && variant.TokensPerSecond > 0 {
			return true
		}
	}
	return false
}

func variantsHaveVRAM(variants []VariantTelemetry) bool {
	for _, variant := range variants {
		if variant.Available && variant.PeakVRAMGB > 0 {
			return true
		}
	}
	return false
}

func round6(value float64) float64 {
	return math.Round(value*1000000) / 1000000
}
