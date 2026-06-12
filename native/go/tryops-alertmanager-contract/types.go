package main

const schemaVersion = "tryops.native_alertmanager_contract.v1"

type Config struct {
	Root             string
	AlertmanagerPath string
	PrometheusPath   string
	ComposePath      string
	OutputPath       string
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

type AlertmanagerSummary struct {
	Path            string   `json:"path"`
	DefaultReceiver string   `json:"default_receiver"`
	GroupBy         []string `json:"group_by"`
	Receivers       []string `json:"receivers"`
	PageWebhookURL  string   `json:"page_webhook_url"`
	Matchers        []string `json:"matchers"`
	InhibitRules    int      `json:"inhibit_rules"`
}

type PrometheusSummary struct {
	Path           string   `json:"path"`
	AlertTargets   []string `json:"alertmanager_targets"`
	RuleFiles      []string `json:"rule_files"`
	ScrapeJobs     []string `json:"scrape_jobs"`
	AlertRuleCount int      `json:"alert_rule_count"`
	Severities     []string `json:"severities"`
	Workloads      []string `json:"workloads"`
}

type ComposeSummary struct {
	Path          string   `json:"path"`
	ServiceImage  string   `json:"service_image"`
	Ports         []string `json:"ports"`
	Volumes       []string `json:"volumes"`
	PrometheusDep string   `json:"prometheus_depends_on_alertmanager"`
}

type ReportSummary struct {
	PassedChecks    int `json:"passed_checks"`
	FailedChecks    int `json:"failed_checks"`
	TotalChecks     int `json:"total_checks"`
	AlertRules      int `json:"alert_rules"`
	PageReceivers   int `json:"page_receivers"`
	TicketReceivers int `json:"ticket_receivers"`
}

type Report struct {
	SchemaVersion string              `json:"schema_version"`
	GeneratedAt   string              `json:"generated_at"`
	Passed        bool                `json:"passed"`
	CoverageLevel string              `json:"coverage_level"`
	Research      []ResearchSource    `json:"research"`
	Alertmanager  AlertmanagerSummary `json:"alertmanager"`
	Prometheus    PrometheusSummary   `json:"prometheus"`
	Compose       ComposeSummary      `json:"compose"`
	Summary       ReportSummary       `json:"summary"`
	Checks        []Check             `json:"checks"`
	Notes         []string            `json:"notes"`
}
