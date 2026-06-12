package main

const schemaVersion = "tryops.native_observability_contract.v1"

type Config struct {
	Root            string
	CollectorPath   string
	ComposePath     string
	PrometheusPath  string
	TraceSamplePath string
	APISpanPath     string
	APILogPath      string
	GatewayLogPath  string
	OutputPath      string
	ProductionReady bool
	CoverageLevel   string
	ResearchRefresh string
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

type CollectorSummary struct {
	Path             string   `json:"path"`
	Receivers        []string `json:"receivers"`
	Processors       []string `json:"processors"`
	Exporters        []string `json:"exporters"`
	Pipelines        []string `json:"pipelines"`
	OTLPGRPCEndpoint string   `json:"otlp_grpc_endpoint"`
	OTLPHTTPEndpoint string   `json:"otlp_http_endpoint"`
	FileLogIncludes  []string `json:"filelog_includes"`
	HealthEndpoint   string   `json:"health_endpoint"`
}

type ComposeSummary struct {
	Path            string   `json:"path"`
	ServiceImage    string   `json:"service_image"`
	Ports           []string `json:"ports"`
	Volumes         []string `json:"volumes"`
	PrometheusNeeds string   `json:"prometheus_depends_on_otel"`
}

type PrometheusSummary struct {
	Path      string   `json:"path"`
	JobName   string   `json:"job_name"`
	Targets   []string `json:"targets"`
	RuleFiles []string `json:"rule_files"`
}

type CorrelationSummary struct {
	TraceSamplePath    string   `json:"trace_sample_path"`
	APISpanPath        string   `json:"api_span_path"`
	APILogPath         string   `json:"api_log_path"`
	GatewayLogPath     string   `json:"gateway_log_path"`
	APISpans           int      `json:"api_spans"`
	APILogs            int      `json:"api_logs"`
	GatewayLogs        int      `json:"gateway_logs"`
	SharedTraceIDs     []string `json:"shared_trace_ids"`
	ServiceNames       []string `json:"service_names"`
	ModelCallObserved  bool     `json:"model_call_observed"`
	RawPayloadRedacted bool     `json:"raw_payload_redacted"`
}

type ReportSummary struct {
	PassedChecks       int `json:"passed_checks"`
	FailedChecks       int `json:"failed_checks"`
	TotalChecks        int `json:"total_checks"`
	CollectorPipelines int `json:"collector_pipelines"`
	CorrelatedTraces   int `json:"correlated_traces"`
	StructuredLogs     int `json:"structured_logs"`
}

type Report struct {
	SchemaVersion   string             `json:"schema_version"`
	GeneratedAt     string             `json:"generated_at"`
	Passed          bool               `json:"passed"`
	ProductionReady bool               `json:"production_ready"`
	CoverageLevel   string             `json:"coverage_level"`
	Research        []ResearchSource   `json:"research"`
	Collector       CollectorSummary   `json:"collector"`
	Compose         ComposeSummary     `json:"compose"`
	Prometheus      PrometheusSummary  `json:"prometheus"`
	Correlation     CorrelationSummary `json:"correlation"`
	Summary         ReportSummary      `json:"summary"`
	Checks          []Check            `json:"checks"`
	Notes           []string           `json:"notes"`
}
