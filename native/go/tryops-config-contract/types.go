package main

type Config struct {
	Root        string
	ComposePath string
	OutputPath  string
}

type composeFile struct {
	Services map[string]composeService `yaml:"services"`
	Volumes  map[string]interface{}    `yaml:"volumes"`
	Secrets  map[string]composeSecret  `yaml:"secrets"`
	Raw      string                    `yaml:"-"`
}

type composeService struct {
	Image       string                 `yaml:"image"`
	Build       interface{}            `yaml:"build"`
	Command     interface{}            `yaml:"command"`
	Restart     string                 `yaml:"restart"`
	Environment environmentMap         `yaml:"environment"`
	Ports       []string               `yaml:"ports"`
	Volumes     []string               `yaml:"volumes"`
	Secrets     secretRefs             `yaml:"secrets"`
	Healthcheck map[string]interface{} `yaml:"healthcheck"`
	DependsOn   dependsOnMap           `yaml:"depends_on"`
}

type environmentMap map[string]string

type dependsOnMap map[string]string

type secretRefs []string

type composeSecret struct {
	Environment string `yaml:"environment"`
	File        string `yaml:"file"`
}

type serviceContract struct {
	Name            string
	RequiredEnv     []string
	RequiredPorts   []string
	RequireHealth   bool
	RequiredDepends map[string]string
	RequiredSecrets []string
}

type secretContract struct {
	Name        string
	Environment string
}

type contractCheck struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type serviceSummary struct {
	Name            string            `json:"name"`
	RequiredEnv     []string          `json:"required_env,omitempty"`
	RequiredPorts   []string          `json:"required_ports,omitempty"`
	RequireHealth   bool              `json:"require_health"`
	RequiredDepends map[string]string `json:"required_depends,omitempty"`
	RequiredSecrets []string          `json:"required_secrets,omitempty"`
}

type secretSummary struct {
	Name        string `json:"name"`
	Environment string `json:"environment,omitempty"`
}

type contractReport struct {
	SchemaVersion string           `json:"schema_version"`
	GeneratedAt   string           `json:"generated_at"`
	Passed        bool             `json:"passed"`
	CoverageLevel string           `json:"coverage_level"`
	ComposePath   string           `json:"compose_path"`
	Services      []serviceSummary `json:"services"`
	Secrets       []secretSummary  `json:"secrets,omitempty"`
	Checks        []contractCheck  `json:"checks"`
	Notes         []string         `json:"notes"`
}
