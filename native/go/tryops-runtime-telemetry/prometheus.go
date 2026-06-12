package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func renderPrometheus(llm LLMTelemetry, gpu GPUTelemetry) string {
	lines := []string{
		"# HELP tryops_llm_tokens_per_second LLM output throughput from native telemetry evidence.",
		"# TYPE tryops_llm_tokens_per_second gauge",
		fmt.Sprintf("tryops_llm_tokens_per_second{source=\"benchmark\",variant=\"baseline\"} %.6f", llm.Benchmark.TokensPerSecond),
	}
	for _, variant := range llm.Variants {
		if !variant.Available {
			continue
		}
		lines = append(lines, fmt.Sprintf(
			"tryops_llm_tokens_per_second{source=\"pareto\",variant=\"%s\"} %.6f",
			escapeLabel(variant.Variant),
			variant.TokensPerSecond,
		))
	}
	lines = append(lines,
		"# HELP tryops_llm_peak_vram_gb Peak LLM VRAM by variant from native telemetry evidence.",
		"# TYPE tryops_llm_peak_vram_gb gauge",
	)
	for _, variant := range llm.Variants {
		if !variant.Available {
			continue
		}
		lines = append(lines, fmt.Sprintf(
			"tryops_llm_peak_vram_gb{variant=\"%s\"} %.6f",
			escapeLabel(variant.Variant),
			variant.PeakVRAMGB,
		))
	}
	lines = append(lines,
		"# HELP tryops_gpu_memory_used_bytes Current GPU memory used from nvidia-smi.",
		"# TYPE tryops_gpu_memory_used_bytes gauge",
		"# HELP tryops_gpu_memory_total_bytes Current GPU memory total from nvidia-smi.",
		"# TYPE tryops_gpu_memory_total_bytes gauge",
		"# HELP tryops_gpu_utilization_ratio Current GPU compute utilization ratio from nvidia-smi.",
		"# TYPE tryops_gpu_utilization_ratio gauge",
		"# HELP tryops_gpu_power_watts Current GPU power draw from nvidia-smi.",
		"# TYPE tryops_gpu_power_watts gauge",
	)
	for _, device := range gpu.Devices {
		labels := fmt.Sprintf("gpu=\"%s\",name=\"%s\"", escapeLabel(device.Index), escapeLabel(device.Name))
		lines = append(lines,
			fmt.Sprintf("tryops_gpu_memory_used_bytes{%s} %.0f", labels, device.MemoryUsedMiB*1024*1024),
			fmt.Sprintf("tryops_gpu_memory_total_bytes{%s} %.0f", labels, device.MemoryTotalMiB*1024*1024),
			fmt.Sprintf("tryops_gpu_utilization_ratio{%s} %.6f", labels, device.ComputeUtilization),
			fmt.Sprintf("tryops_gpu_power_watts{%s} %.6f", labels, device.PowerDrawWatts),
		)
	}
	lines = append(lines, "")
	return strings.Join(lines, "\n")
}

func writePrometheus(path string, body string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(body), 0o644)
}

func escapeLabel(value string) string {
	value = strings.ReplaceAll(value, "\\", "\\\\")
	value = strings.ReplaceAll(value, "\n", "\\n")
	value = strings.ReplaceAll(value, "\"", "\\\"")
	return value
}
