package main

type BenchmarkReport struct {
	SchemaVersion string                    `json:"schema_version"`
	CreatedAt     string                    `json:"created_at"`
	Load          map[string]int            `json:"load"`
	Scenarios     map[string]ScenarioReport `json:"scenarios"`
}

type ScenarioReport struct {
	Description string                `json:"description"`
	Endpoint    string                `json:"endpoint"`
	Results     map[string]LoadResult `json:"results"`
	Speedup     *SpeedupReport        `json:"native_speedup,omitempty"`
}

type LoadResult struct {
	Requests       int            `json:"requests"`
	Errors         int            `json:"errors"`
	ElapsedSeconds float64        `json:"elapsed_s"`
	RequestsPerSec float64        `json:"requests_per_sec"`
	LatencyMs      LatencySummary `json:"latency_ms"`
}

type LatencySummary struct {
	P50  float64 `json:"p50"`
	P95  float64 `json:"p95"`
	P99  float64 `json:"p99"`
	Min  float64 `json:"min"`
	Max  float64 `json:"max"`
	Mean float64 `json:"mean"`
}

type SpeedupReport struct {
	ThroughputX float64 `json:"throughput_x"`
	P50LatencyX float64 `json:"p50_latency_x"`
	P99LatencyX float64 `json:"p99_latency_x"`
}

type GatePolicy struct {
	SchemaVersion string           `json:"schema_version,omitempty"`
	Rules         []ScenarioPolicy `json:"rules"`
}

type ScenarioPolicy struct {
	Name                 string   `json:"name"`
	Scenario             string   `json:"scenario"`
	Target               string   `json:"target"`
	MaxErrors            int      `json:"max_errors"`
	MaxErrorRate         float64  `json:"max_error_rate"`
	MaxP95MS             float64  `json:"max_p95_ms"`
	MaxP99MS             float64  `json:"max_p99_ms"`
	MinRequestsPerSecond float64  `json:"min_requests_per_second"`
	CompareTarget        string   `json:"compare_target,omitempty"`
	MinThroughputRatio   float64  `json:"min_throughput_ratio,omitempty"`
	MaxP95Ratio          float64  `json:"max_p95_ratio,omitempty"`
	MaxP99Ratio          float64  `json:"max_p99_ratio,omitempty"`
	RequiredSpeedup      *float64 `json:"required_speedup,omitempty"`
}

type RuleResult struct {
	Name         string                 `json:"name"`
	Scenario     string                 `json:"scenario"`
	Target       string                 `json:"target"`
	Passed       bool                   `json:"passed"`
	Endpoint     string                 `json:"endpoint,omitempty"`
	Measurements map[string]float64     `json:"measurements"`
	Thresholds   map[string]float64     `json:"thresholds"`
	Failures     []string               `json:"failures,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

type GateSummary struct {
	TotalRules  int `json:"total_rules"`
	PassedRules int `json:"passed_rules"`
	FailedRules int `json:"failed_rules"`
}

type GateReport struct {
	SchemaVersion       string       `json:"schema_version"`
	GeneratedAt         string       `json:"generated_at"`
	InputPath           string       `json:"input_path"`
	InputSchemaVersion  string       `json:"input_schema_version"`
	InputCreatedAt      string       `json:"input_created_at,omitempty"`
	Passed              bool         `json:"passed"`
	Summary             GateSummary  `json:"summary"`
	PolicySchemaVersion string       `json:"policy_schema_version,omitempty"`
	Rules               []RuleResult `json:"rules"`
}
