package main

type Config struct {
	Requests        int
	Concurrency     int
	GatewayBin      string
	PythonBin       string
	GatewayPort     int
	PythonPort      int
	OutputPath      string
	RequireExternal bool
	MaxErrorRate    float64
	DefaultMaxP95MS float64
	DefaultMaxP99MS float64
	DefaultMinRPS   float64
}

type HTTPRequestSpec struct {
	Name           string
	Method         string
	URL            string
	Headers        map[string]string
	Body           []byte
	ExpectedStatus int
	Weight         int
	MaxP95MS       float64
	MaxP99MS       float64
	MinRPS         float64
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
	ErrorRate      float64        `json:"error_rate"`
	ElapsedSeconds float64        `json:"elapsed_s"`
	RequestsPerSec float64        `json:"requests_per_sec"`
	LatencyMs      LatencySummary `json:"latency_ms"`
}

type ScenarioResult struct {
	Name    string            `json:"name"`
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Weight  int               `json:"weight"`
	Load    LoadResult        `json:"load"`
	SLO     SLOResult         `json:"slo"`
	Headers map[string]string `json:"headers,omitempty"`
}

type SLOResult struct {
	Passed     bool               `json:"passed"`
	Failures   []string           `json:"failures,omitempty"`
	Thresholds map[string]float64 `json:"thresholds"`
	Observed   map[string]float64 `json:"observed"`
}

type ExternalTool struct {
	Name      string `json:"name"`
	Required  bool   `json:"required"`
	Available bool   `json:"available"`
	Path      string `json:"path,omitempty"`
	Note      string `json:"note,omitempty"`
}

type Summary struct {
	PassedScenarios int     `json:"passed_scenarios"`
	TotalScenarios  int     `json:"total_scenarios"`
	TotalRequests   int     `json:"total_requests"`
	TotalErrors     int     `json:"total_errors"`
	WorstP95MS      float64 `json:"worst_p95_ms"`
	WorstP99MS      float64 `json:"worst_p99_ms"`
	MinRPS          float64 `json:"min_rps"`
	ExternalReady   bool    `json:"external_ready"`
}

type Report struct {
	SchemaVersion string              `json:"schema_version"`
	GeneratedAt   string              `json:"generated_at"`
	Passed        bool                `json:"passed"`
	CoverageLevel string              `json:"coverage_level"`
	Driver        map[string]string   `json:"driver"`
	Load          map[string]int      `json:"load"`
	Summary       Summary             `json:"summary"`
	Scenarios     []ScenarioResult    `json:"scenarios"`
	ExternalTools []ExternalTool      `json:"external_tools"`
	Research      []map[string]string `json:"research"`
	Notes         []string            `json:"notes"`
}
