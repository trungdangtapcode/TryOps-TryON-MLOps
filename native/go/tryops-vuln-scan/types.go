package main

type toolStatus struct {
	Name      string `json:"name"`
	Path      string `json:"path,omitempty"`
	Available bool   `json:"available"`
	Required  bool   `json:"required_for_production"`
}

type scanResult struct {
	Name            string         `json:"name"`
	Tool            string         `json:"tool"`
	Path            string         `json:"path"`
	Passed          bool           `json:"passed"`
	ExitCode        int            `json:"exit_code"`
	DurationMS      int64          `json:"duration_ms"`
	RawOutputPath   string         `json:"raw_output_path,omitempty"`
	Vulnerabilities map[string]int `json:"vulnerabilities,omitempty"`
	Error           string         `json:"error,omitempty"`
}

type vulnerabilityReport struct {
	SchemaVersion        string       `json:"schema_version"`
	GeneratedAt          string       `json:"generated_at"`
	Passed               bool         `json:"passed"`
	CoverageLevel        string       `json:"coverage_level"`
	ProductionReady      bool         `json:"production_ready"`
	MissingRequiredTools []string     `json:"missing_required_tools"`
	Tools                []toolStatus `json:"tools"`
	Scans                []scanResult `json:"scans"`
	Notes                []string     `json:"notes"`
}
