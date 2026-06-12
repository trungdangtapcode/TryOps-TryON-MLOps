package main

type Report struct {
	SchemaVersion string            `json:"schema_version"`
	CreatedAt     string            `json:"created_at"`
	Passed        bool              `json:"passed"`
	Status        string            `json:"status"`
	Driver        DriverInfo        `json:"driver"`
	Runtime       RuntimeInfo       `json:"runtime"`
	Candidates    []CandidateResult `json:"candidates"`
	Summary       Summary           `json:"summary"`
	Research      map[string]string `json:"research_basis"`
	Reasons       []string          `json:"reasons,omitempty"`
}

type DriverInfo struct {
	Name     string `json:"name"`
	Language string `json:"language"`
	Version  string `json:"version"`
}

type RuntimeInfo struct {
	PythonExecutable string             `json:"python_executable"`
	Packages         map[string]Package `json:"packages"`
	GPUs             []GPUInfo          `json:"gpus,omitempty"`
}

type Package struct {
	Available bool   `json:"available"`
	Version   string `json:"version,omitempty"`
}

type GPUInfo struct {
	Name         string `json:"name"`
	MemoryMiB    string `json:"memory_mib"`
	Driver       string `json:"driver"`
	RawLine      string `json:"raw_line"`
	QueryError   string `json:"query_error,omitempty"`
	QuerySkipped bool   `json:"query_skipped,omitempty"`
}

type CandidateSpec struct {
	Method string
	Repo   string
}

type CandidateResult struct {
	Method          string             `json:"method"`
	Repo            string             `json:"repo"`
	ConfigURL       string             `json:"config_url"`
	Reachable       bool               `json:"reachable"`
	Suitable        bool               `json:"suitable"`
	LoadReady       bool               `json:"load_ready"`
	StatusCode      int                `json:"status_code,omitempty"`
	HTTPBytes       int                `json:"http_bytes,omitempty"`
	ModelType       string             `json:"model_type,omitempty"`
	Architecture    []string           `json:"architecture,omitempty"`
	License         string             `json:"license,omitempty"`
	Quantization    QuantizationConfig `json:"quantization"`
	ArtifactChecks  []ArtifactCheck    `json:"artifact_checks,omitempty"`
	LoaderPackages  []string           `json:"loader_packages,omitempty"`
	MissingPackages []string           `json:"missing_packages,omitempty"`
	Reasons         []string           `json:"reasons,omitempty"`
	Error           string             `json:"error,omitempty"`
}

type QuantizationConfig struct {
	Method    string `json:"method,omitempty"`
	Bits      int    `json:"bits,omitempty"`
	GroupSize int    `json:"group_size,omitempty"`
	Version   string `json:"version,omitempty"`
	ZeroPoint *bool  `json:"zero_point,omitempty"`
	Sym       *bool  `json:"sym,omitempty"`
}

type ArtifactCheck struct {
	Path          string `json:"path"`
	URL           string `json:"url"`
	Reachable     bool   `json:"reachable"`
	StatusCode    int    `json:"status_code,omitempty"`
	ContentLength int64  `json:"content_length,omitempty"`
	Error         string `json:"error,omitempty"`
}

type Summary struct {
	TotalCandidates     int      `json:"total_candidates"`
	SuitableCandidates  int      `json:"suitable_candidates"`
	LoadReadyCandidates int      `json:"load_ready_candidates"`
	GPTQStatus          string   `json:"gptq_status"`
	AWQStatus           string   `json:"awq_status"`
	MissingPackages     []string `json:"missing_packages,omitempty"`
}
