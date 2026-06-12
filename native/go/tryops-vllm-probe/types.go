package main

type Report struct {
	SchemaVersion string            `json:"schema_version"`
	CreatedAt     string            `json:"created_at"`
	Passed        bool              `json:"passed"`
	Status        string            `json:"status"`
	Driver        DriverInfo        `json:"driver"`
	Target        TargetInfo        `json:"target"`
	Environment   EnvironmentInfo   `json:"environment"`
	Checks        []CheckResult     `json:"checks"`
	Models        ModelsResult      `json:"models"`
	Chat          ChatResult        `json:"chat"`
	Load          LoadResult        `json:"load"`
	Metrics       MetricsResult     `json:"metrics"`
	Reasons       []string          `json:"reasons,omitempty"`
	Research      map[string]string `json:"research_basis"`
}

type DriverInfo struct {
	Name     string `json:"name"`
	Language string `json:"language"`
	Version  string `json:"version"`
}

type TargetInfo struct {
	BaseURL     string `json:"base_url"`
	MetricsURL  string `json:"metrics_url"`
	Model       string `json:"model"`
	Prompt      string `json:"prompt"`
	MaxTokens   int    `json:"max_tokens"`
	Requests    int    `json:"requests"`
	Concurrency int    `json:"concurrency"`
}

type EnvironmentInfo struct {
	VLLMBinaryAvailable bool      `json:"vllm_binary_available"`
	VLLMBinaryPath      string    `json:"vllm_binary_path,omitempty"`
	GPUs                []GPUInfo `json:"gpus,omitempty"`
}

type GPUInfo struct {
	Name         string `json:"name"`
	MemoryMiB    string `json:"memory_mib"`
	Driver       string `json:"driver"`
	RawLine      string `json:"raw_line"`
	QueryError   string `json:"query_error,omitempty"`
	QuerySkipped bool   `json:"query_skipped,omitempty"`
}

type CheckResult struct {
	Name         string  `json:"name"`
	Passed       bool    `json:"passed"`
	Skipped      bool    `json:"skipped,omitempty"`
	StatusCode   int     `json:"status_code,omitempty"`
	LatencyMS    float64 `json:"latency_ms,omitempty"`
	Error        string  `json:"error,omitempty"`
	Detail       string  `json:"detail,omitempty"`
	ResponseSize int     `json:"response_size_bytes,omitempty"`
}

type ModelsResult struct {
	Available bool     `json:"available"`
	ModelIDs  []string `json:"model_ids,omitempty"`
	Selected  string   `json:"selected,omitempty"`
}

type ChatResult struct {
	Attempted        bool    `json:"attempted"`
	Passed           bool    `json:"passed"`
	StatusCode       int     `json:"status_code,omitempty"`
	LatencyMS        float64 `json:"latency_ms,omitempty"`
	PromptTokens     int     `json:"prompt_tokens,omitempty"`
	CompletionTokens int     `json:"completion_tokens,omitempty"`
	TotalTokens      int     `json:"total_tokens,omitempty"`
	Error            string  `json:"error,omitempty"`
	ResponsePreview  string  `json:"response_preview,omitempty"`
}

type LoadResult struct {
	Attempted          bool    `json:"attempted"`
	Requests           int     `json:"requests"`
	Concurrency        int     `json:"concurrency"`
	Succeeded          int     `json:"succeeded"`
	Failed             int     `json:"failed"`
	LatencyP50MS       float64 `json:"latency_p50_ms,omitempty"`
	LatencyP95MS       float64 `json:"latency_p95_ms,omitempty"`
	LatencyMaxMS       float64 `json:"latency_max_ms,omitempty"`
	CompletionTokens   int     `json:"completion_tokens,omitempty"`
	TokensPerSecond    float64 `json:"tokens_per_second,omitempty"`
	WallClockSeconds   float64 `json:"wall_clock_seconds,omitempty"`
	FirstFailureReason string  `json:"first_failure_reason,omitempty"`
}

type MetricsResult struct {
	Attempted           bool     `json:"attempted"`
	Available           bool     `json:"available"`
	StatusCode          int      `json:"status_code,omitempty"`
	LatencyMS           float64  `json:"latency_ms,omitempty"`
	ContainsVLLMMetrics bool     `json:"contains_vllm_metrics"`
	SampleMetricNames   []string `json:"sample_metric_names,omitempty"`
	Error               string   `json:"error,omitempty"`
}
