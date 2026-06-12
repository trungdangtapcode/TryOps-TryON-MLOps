package main

type BenchmarkConfig struct {
	Requests    int
	Concurrency int
	GatewayBin  string
	PythonBin   string
	GatewayPort int
	PythonPort  int
	Output      string
}

type HTTPRequestSpec struct {
	Method         string
	URL            string
	Headers        map[string]string
	Body           []byte
	ExpectedStatus int
}

type LatencySummary struct {
	P50  float64 `json:"p50"`
	P95  float64 `json:"p95"`
	P99  float64 `json:"p99"`
	Min  float64 `json:"min"`
	Max  float64 `json:"max"`
	Mean float64 `json:"mean"`
}

type LoadResult struct {
	Requests       int            `json:"requests"`
	Errors         int            `json:"errors"`
	ElapsedSeconds float64        `json:"elapsed_s"`
	RequestsPerSec float64        `json:"requests_per_sec"`
	LatencyMs      LatencySummary `json:"latency_ms"`
}

type ScenarioReport struct {
	Description string                `json:"description"`
	Endpoint    string                `json:"endpoint"`
	Results     map[string]LoadResult `json:"results"`
	Speedup     *SpeedupReport        `json:"native_speedup,omitempty"`
	Notes       []string              `json:"notes,omitempty"`
}

type SpeedupReport struct {
	ThroughputX float64 `json:"throughput_x"`
	P50LatencyX float64 `json:"p50_latency_x"`
	P99LatencyX float64 `json:"p99_latency_x"`
}

type BenchmarkReport struct {
	SchemaVersion string                    `json:"schema_version"`
	CreatedAt     string                    `json:"created_at"`
	Driver        map[string]string         `json:"driver"`
	Load          map[string]int            `json:"load"`
	Scenarios     map[string]ScenarioReport `json:"scenarios"`
	Notes         []string                  `json:"notes"`
}
