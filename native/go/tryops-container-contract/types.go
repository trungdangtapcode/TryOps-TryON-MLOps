package main

type Manifest struct {
	SchemaVersion string      `json:"schema_version"`
	GeneratedFor  string      `json:"generated_for"`
	Images        []ImageSpec `json:"images"`
}

type ImageSpec struct {
	Role           string   `json:"role"`
	Image          string   `json:"image"`
	Dockerfile     string   `json:"dockerfile"`
	Context        string   `json:"context"`
	Runtime        string   `json:"runtime"`
	ComposeService string   `json:"compose_service"`
	RequiredStage  string   `json:"required_stage"`
	SourcePaths    []string `json:"source_paths"`
	Ports          []int    `json:"ports"`
}

type ComposeFile struct {
	Services map[string]ComposeService `yaml:"services"`
}

type ComposeService struct {
	Image       string                 `yaml:"image"`
	Build       map[string]interface{} `yaml:"build"`
	Profiles    []string               `yaml:"profiles"`
	Ports       []interface{}          `yaml:"ports"`
	Environment interface{}            `yaml:"environment"`
	Healthcheck map[string]interface{} `yaml:"healthcheck"`
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type ResearchSource struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type Summary struct {
	RequiredRoles int            `json:"required_roles"`
	ManifestRoles int            `json:"manifest_roles"`
	ComposeRoles  int            `json:"compose_roles"`
	PassedChecks  int            `json:"passed_checks"`
	FailedChecks  int            `json:"failed_checks"`
	ByRuntime     map[string]int `json:"by_runtime"`
}

type Report struct {
	SchemaVersion string           `json:"schema_version"`
	GeneratedAt   string           `json:"generated_at"`
	Passed        bool             `json:"passed"`
	CoverageLevel string           `json:"coverage_level"`
	Manifest      string           `json:"manifest"`
	Compose       string           `json:"compose"`
	Research      []ResearchSource `json:"research"`
	Summary       Summary          `json:"summary"`
	Checks        []Check          `json:"checks"`
	Images        []ImageSpec      `json:"images"`
}
