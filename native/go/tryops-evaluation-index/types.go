package main

type evaluationIndex struct {
	SchemaVersion string                    `json:"schema_version"`
	GeneratedAt   string                    `json:"generated_at"`
	SourceRoots   []string                  `json:"source_roots"`
	TotalReports  int                       `json:"total_reports"`
	StatusCounts  map[string]int            `json:"status_counts"`
	CategoryCount map[string]int            `json:"category_counts"`
	Highlights    map[string]artifactReport `json:"highlights"`
	Optimization  *optimizationPanel        `json:"optimization_panel,omitempty"`
	PipelineRuns  []pipelineRun             `json:"pipeline_runs,omitempty"`
	Reports       []artifactReport          `json:"reports"`
}

type artifactReport struct {
	Name          string            `json:"name"`
	Title         string            `json:"title"`
	Category      string            `json:"category"`
	Path          string            `json:"path"`
	SchemaVersion string            `json:"schema_version,omitempty"`
	CreatedAt     string            `json:"created_at,omitempty"`
	Status        string            `json:"status"`
	Summary       []summaryItem     `json:"summary,omitempty"`
	Metadata      map[string]string `json:"metadata,omitempty"`
}

type summaryItem struct {
	Label string `json:"label"`
	Value string `json:"value"`
}

type pipelineRun struct {
	RunID          string            `json:"run_id"`
	RunName        string            `json:"run_name,omitempty"`
	CandidateID    string            `json:"candidate_id,omitempty"`
	Workload       string            `json:"workload,omitempty"`
	JobName        string            `json:"job_name,omitempty"`
	EventType      string            `json:"event_type,omitempty"`
	EventTime      string            `json:"event_time,omitempty"`
	TraceID        string            `json:"trace_id,omitempty"`
	CodeVersion    string            `json:"code_version,omitempty"`
	DatasetVersion string            `json:"dataset_version,omitempty"`
	ModelName      string            `json:"model_name,omitempty"`
	ModelVersion   string            `json:"model_version,omitempty"`
	RiskStatus     string            `json:"risk_status,omitempty"`
	Signed         bool              `json:"signed"`
	Paths          map[string]string `json:"paths"`
}

type optimizationPanel struct {
	RecommendedVariant string                `json:"recommended_variant"`
	Recommendation     string                `json:"recommendation"`
	CarbonGateVerdict  string                `json:"carbon_gate_verdict"`
	GreenestVariant    string                `json:"greenest_variant,omitempty"`
	ModelID            string                `json:"model_id,omitempty"`
	JudgeBackend       string                `json:"judge_backend,omitempty"`
	Ranking            []string              `json:"ranking,omitempty"`
	Variants           []optimizationVariant `json:"variants"`
	Sources            map[string]string     `json:"sources"`
}

type optimizationVariant struct {
	Variant             string  `json:"variant"`
	Adapter             string  `json:"adapter,omitempty"`
	LeaderboardRank     int     `json:"leaderboard_rank,omitempty"`
	QualityScore        float64 `json:"quality_score,omitempty"`
	LatencyP50MS        float64 `json:"latency_p50_ms,omitempty"`
	TokensPerSecond     float64 `json:"tokens_per_second,omitempty"`
	PeakVRAMGB          float64 `json:"peak_vram_gb,omitempty"`
	EnergyWhPer1KTokens float64 `json:"energy_wh_per_1k_tokens,omitempty"`
	SCIGPer1KTokens     float64 `json:"sci_g_per_1k_tokens,omitempty"`
	SLOVerdict          string  `json:"slo_verdict,omitempty"`
	ParetoFrontier      bool    `json:"pareto_frontier"`
	Recommended         bool    `json:"recommended"`
}
