package main

type BenchmarkReport struct {
	SchemaVersion string                    `json:"schema_version"`
	CreatedAt     string                    `json:"created_at"`
	Driver        map[string]string         `json:"driver,omitempty"`
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

type SLOGateReport struct {
	SchemaVersion string         `json:"schema_version"`
	GeneratedAt   string         `json:"generated_at"`
	Passed        bool           `json:"passed"`
	Summary       SLOGateSummary `json:"summary"`
}

type SLOGateSummary struct {
	TotalRules  int `json:"total_rules"`
	PassedRules int `json:"passed_rules"`
	FailedRules int `json:"failed_rules"`
}

type PerfStatsReport struct {
	SchemaVersion string          `json:"schema_version"`
	CreatedAt     string          `json:"created_at"`
	NativeStats   NativePerfStats `json:"native_stats"`
	SampleCount   int             `json:"sample_count"`
}

type NativePerfStats struct {
	Available       bool             `json:"available"`
	CLIPath         string           `json:"cli_path"`
	Count           int              `json:"count"`
	ReturnCode      int              `json:"returncode"`
	SchemaVersion   string           `json:"schema_version"`
	SLO             NativePerfSLO    `json:"slo"`
	LatencyMs       NativeLatency    `json:"latency_ms"`
	TokensPerSecond NativeThroughput `json:"tokens_per_second"`
}

type NativePerfSLO struct {
	Evaluated          bool    `json:"evaluated"`
	LatencyP95MSMax    float64 `json:"latency_p95_ms_max"`
	LatencyPass        bool    `json:"latency_pass"`
	ThroughputPass     bool    `json:"throughput_pass"`
	TokensPerSecondMin float64 `json:"tokens_per_second_min"`
	Verdict            string  `json:"verdict"`
}

type NativeLatency struct {
	Max  float64 `json:"max"`
	Mean float64 `json:"mean"`
	Min  float64 `json:"min"`
	P50  float64 `json:"p50"`
	P95  float64 `json:"p95"`
	P99  float64 `json:"p99"`
}

type NativeThroughput struct {
	Count int     `json:"count"`
	Mean  float64 `json:"mean"`
	Min   float64 `json:"min"`
}

type ConfigContractReport struct {
	SchemaVersion string                 `json:"schema_version"`
	GeneratedAt   string                 `json:"generated_at"`
	Passed        bool                   `json:"passed"`
	CoverageLevel string                 `json:"coverage_level"`
	Services      []ConfigServiceSummary `json:"services"`
	Checks        []ConfigCheck          `json:"checks"`
}

type ConfigServiceSummary struct {
	Name string `json:"name"`
}

type ConfigCheck struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type ArtifactSet struct {
	Benchmark      BenchmarkReport
	SLOGate        SLOGateReport
	PerfStats      PerfStatsReport
	ConfigContract ConfigContractReport
	Inputs         []InputArtifact `json:"inputs"`
}

type InputArtifact struct {
	Name          string `json:"name"`
	Path          string `json:"path"`
	Present       bool   `json:"present"`
	SchemaVersion string `json:"schema_version,omitempty"`
	CreatedAt     string `json:"created_at,omitempty"`
	Bytes         int64  `json:"bytes,omitempty"`
	Error         string `json:"error,omitempty"`
}

type BudgetResult struct {
	Name           string             `json:"name"`
	Language       string             `json:"language"`
	Category       string             `json:"category"`
	SourceArtifact string             `json:"source_artifact"`
	Passed         bool               `json:"passed"`
	Measurements   map[string]float64 `json:"measurements"`
	Thresholds     map[string]float64 `json:"thresholds"`
	Failures       []string           `json:"failures,omitempty"`
	Evidence       map[string]string  `json:"evidence,omitempty"`
}

type BudgetSummary struct {
	TotalBudgets  int            `json:"total_budgets"`
	PassedBudgets int            `json:"passed_budgets"`
	FailedBudgets int            `json:"failed_budgets"`
	ByLanguage    map[string]int `json:"by_language"`
}

type CIContract struct {
	ArtifactName    string   `json:"artifact_name"`
	JSONPath        string   `json:"json_path"`
	MarkdownPath    string   `json:"markdown_path"`
	StepSummaryPath string   `json:"step_summary_path,omitempty"`
	Notes           []string `json:"notes"`
}

type PerformanceBudgetReport struct {
	SchemaVersion string          `json:"schema_version"`
	GeneratedAt   string          `json:"generated_at"`
	Passed        bool            `json:"passed"`
	CoverageLevel string          `json:"coverage_level"`
	Summary       BudgetSummary   `json:"summary"`
	Inputs        []InputArtifact `json:"inputs"`
	Budgets       []BudgetResult  `json:"budgets"`
	CI            CIContract      `json:"ci"`
}
