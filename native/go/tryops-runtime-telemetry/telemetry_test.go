package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestParseNvidiaSMI(t *testing.T) {
	devices := parseNvidiaSMI("0, NVIDIA L4, 512, 23034, 25, 42.5\n")
	if len(devices) != 1 {
		t.Fatalf("unexpected devices: %#v", devices)
	}
	device := devices[0]
	if device.Name != "NVIDIA L4" || device.MemoryUsedMiB != 512 || device.ComputeUtilization != 0.25 {
		t.Fatalf("unexpected device: %#v", device)
	}
	if device.MemoryUtilization <= 0 {
		t.Fatalf("expected memory utilization: %#v", device)
	}
}

func TestBuildReportAndPrometheus(t *testing.T) {
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "bench.json"), `{
		"schema_version":"tryops.llm_benchmark.v1",
		"summary":{"tokens_per_second":123.5,"memory_gb":0.25,"latency_p95_ms":12,"phase_timing":{"available":true}}
	}`)
	writeFile(t, filepath.Join(root, "pareto.json"), `{
		"schema_version":"tryops.llm_pareto.v1",
		"variants":[
			{"variant":"none","adapter":"transformers-none","available":true,"tokens_per_second":20,"peak_vram_gb":1.5,"latency_p50_ms":100,"native_perf_stats":{"available":true},"slo":{"verdict":"pass"}},
			{"variant":"4bit","adapter":"transformers-4bit","available":true,"tokens_per_second":40,"peak_vram_gb":0.5,"latency_p50_ms":80,"native_perf_stats":{"available":true},"slo":{"verdict":"pass"}}
		]
	}`)
	fakeSMI := filepath.Join(root, "nvidia-smi")
	writeExecutable(t, fakeSMI, "#!/bin/sh\nprintf '0, NVIDIA L4, 10, 100, 50, 20.5\\n'\n")
	cfg := Config{
		Root:            root,
		BenchmarkPath:   "bench.json",
		ParetoPath:      "pareto.json",
		OutputPath:      "out/report.json",
		PrometheusPath:  "out/report.prom",
		NvidiaSMIBinary: fakeSMI,
	}
	report, prom, err := buildReport(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if !report.Passed {
		t.Fatalf("expected passed report: %#v", report.Checks)
	}
	if report.LLM.VariantCount != 2 || report.LLM.NativeSLOGateCount != 2 {
		t.Fatalf("unexpected llm telemetry: %#v", report.LLM)
	}
	if !report.GPU.Available || len(report.GPU.Devices) != 1 {
		t.Fatalf("unexpected gpu telemetry: %#v", report.GPU)
	}
	if !strings.Contains(prom, "tryops_llm_tokens_per_second") ||
		!strings.Contains(prom, "tryops_gpu_memory_used_bytes") {
		t.Fatalf("unexpected prometheus text: %s", prom)
	}
}

func writeFile(t *testing.T, path string, body string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeExecutable(t *testing.T, path string, body string) {
	t.Helper()
	writeFile(t, path, body)
	if err := os.Chmod(path, 0o755); err != nil {
		t.Fatal(err)
	}
}
