package main

type Config struct {
	RootPath            string
	WorkflowPath        string
	MakefilePath        string
	VulnerabilityPath   string
	SupplyChainPath     string
	LiveSupplyChainPath string
	ContainerReportPath string
	OutputPath          string
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type ToolStatus struct {
	Name      string `json:"name"`
	Path      string `json:"path,omitempty"`
	Available bool   `json:"available"`
	Required  bool   `json:"required_for_production"`
}

type EvidenceRef struct {
	Name          string `json:"name"`
	Path          string `json:"path"`
	SchemaVersion string `json:"schema_version,omitempty"`
	Status        string `json:"status"`
	Detail        string `json:"detail,omitempty"`
}

type ResearchRef struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type Report struct {
	SchemaVersion        string        `json:"schema_version"`
	GeneratedAt          string        `json:"generated_at"`
	Passed               bool          `json:"passed"`
	ProductionReady      bool          `json:"production_ready"`
	CoverageLevel        string        `json:"coverage_level"`
	WorkflowPath         string        `json:"workflow_path"`
	MakefilePath         string        `json:"makefile_path"`
	MissingRequiredTools []string      `json:"missing_required_tools"`
	Tools                []ToolStatus  `json:"tools"`
	Checks               []Check       `json:"checks"`
	Evidence             []EvidenceRef `json:"evidence"`
	Research             []ResearchRef `json:"research"`
	Notes                []string      `json:"notes"`
}
