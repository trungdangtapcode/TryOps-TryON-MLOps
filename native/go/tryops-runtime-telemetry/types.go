package main

type Report struct {
	SchemaVersion  string           `json:"schema_version"`
	GeneratedAt    string           `json:"generated_at"`
	Passed         bool             `json:"passed"`
	CoverageLevel  string           `json:"coverage_level"`
	Sources        Sources          `json:"sources"`
	Research       []ResearchSource `json:"research"`
	LLM            LLMTelemetry     `json:"llm"`
	GPU            GPUTelemetry     `json:"gpu"`
	PrometheusPath string           `json:"prometheus_path"`
	Checks         map[string]bool  `json:"checks"`
}

type Sources struct {
	BenchmarkPath string `json:"benchmark_path"`
	ParetoPath    string `json:"pareto_path"`
	NvidiaSMI     string `json:"nvidia_smi"`
}

type ResearchSource struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type LLMTelemetry struct {
	Benchmark          BenchmarkTelemetry `json:"benchmark"`
	Variants           []VariantTelemetry `json:"variants"`
	BestTokensPerSec   float64            `json:"best_tokens_per_second"`
	MaxPeakVRAMGB      float64            `json:"max_peak_vram_gb"`
	VariantCount       int                `json:"variant_count"`
	NativeSLOGateCount int                `json:"native_slo_gate_count"`
}

type BenchmarkTelemetry struct {
	Available          bool    `json:"available"`
	TokensPerSecond    float64 `json:"tokens_per_second"`
	MemoryGB           float64 `json:"memory_gb"`
	LatencyP95MS       float64 `json:"latency_p95_ms"`
	PhaseTimingPresent bool    `json:"phase_timing_present"`
}

type VariantTelemetry struct {
	Variant            string  `json:"variant"`
	Adapter            string  `json:"adapter,omitempty"`
	Available          bool    `json:"available"`
	TokensPerSecond    float64 `json:"tokens_per_second"`
	PeakVRAMGB         float64 `json:"peak_vram_gb"`
	LatencyP50MS       float64 `json:"latency_p50_ms"`
	NativeStatsPresent bool    `json:"native_stats_present"`
	SLOVerdict         string  `json:"slo_verdict,omitempty"`
}

type GPUTelemetry struct {
	Queried    bool        `json:"queried"`
	Available  bool        `json:"available"`
	BinaryPath string      `json:"binary_path,omitempty"`
	QueryError string      `json:"query_error,omitempty"`
	Devices    []GPUDevice `json:"devices"`
}

type GPUDevice struct {
	Index              string  `json:"index"`
	Name               string  `json:"name"`
	MemoryUsedMiB      float64 `json:"memory_used_mib"`
	MemoryTotalMiB     float64 `json:"memory_total_mib"`
	MemoryUsedGB       float64 `json:"memory_used_gb"`
	MemoryTotalGB      float64 `json:"memory_total_gb"`
	MemoryUtilization  float64 `json:"memory_utilization"`
	ComputeUtilization float64 `json:"compute_utilization"`
	PowerDrawWatts     float64 `json:"power_draw_watts"`
}
