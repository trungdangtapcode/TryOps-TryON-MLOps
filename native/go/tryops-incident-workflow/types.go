package main

const schemaVersion = "tryops.native_incident_workflow.v1"
const errorEventSchema = "tryops.error_event.v1"

type Config struct {
	RootPath       string
	OutputPath     string
	PostmortemPath string
	TemplatePath   string
	RollbackPath   string
	ControllerPath string
	DispatcherPath string
	GeneratedAt    string
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type ResearchRef struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type EvidenceRef struct {
	Name          string `json:"name"`
	Path          string `json:"path"`
	SchemaVersion string `json:"schema_version,omitempty"`
	Status        string `json:"status"`
	Detail        string `json:"detail,omitempty"`
}

type AlertmanagerPayload struct {
	Receiver     string                 `json:"receiver"`
	Status       string                 `json:"status"`
	GroupLabels  map[string]string      `json:"groupLabels"`
	CommonLabels map[string]string      `json:"commonLabels"`
	Alerts       []AlertmanagerAlert    `json:"alerts"`
	ExternalURL  string                 `json:"externalURL,omitempty"`
	Version      string                 `json:"version,omitempty"`
	GroupKey     string                 `json:"groupKey,omitempty"`
	Truncated    int                    `json:"truncatedAlerts,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

type AlertmanagerAlert struct {
	Status       string            `json:"status"`
	Labels       map[string]string `json:"labels"`
	Annotations  map[string]string `json:"annotations"`
	StartsAt     string            `json:"startsAt"`
	EndsAt       string            `json:"endsAt,omitempty"`
	GeneratorURL string            `json:"generatorURL,omitempty"`
	Fingerprint  string            `json:"fingerprint"`
}

type AlertSummary struct {
	Receiver          string   `json:"receiver"`
	Status            string   `json:"status"`
	Severity          string   `json:"severity"`
	Workload          string   `json:"workload"`
	AlertNames        []string `json:"alert_names"`
	AlertCount        int      `json:"alert_count"`
	RunbookURL        string   `json:"runbook_url"`
	ControllerWebhook string   `json:"controller_webhook"`
}

type Exception struct {
	Type       string `json:"type"`
	Message    string `json:"message"`
	Stacktrace string `json:"stacktrace,omitempty"`
}

type ErrorEvent struct {
	SchemaVersion  string            `json:"schema_version"`
	Timestamp      string            `json:"timestamp"`
	EventName      string            `json:"event_name"`
	SeverityText   string            `json:"severity_text"`
	TraceID        string            `json:"trace_id"`
	SpanID         string            `json:"span_id"`
	ServiceName    string            `json:"service_name"`
	ServiceVersion string            `json:"service_version"`
	Fingerprint    string            `json:"fingerprint"`
	Exception      Exception         `json:"exception"`
	Attributes     map[string]string `json:"attributes"`
}

type ExternalTrackerSummary struct {
	Configured bool   `json:"configured"`
	Provider   string `json:"provider"`
	Mode       string `json:"mode"`
	Detail     string `json:"detail"`
}

type ErrorTrackingSummary struct {
	LocalSchemaVersion string                 `json:"local_schema_version"`
	EventCount         int                    `json:"event_count"`
	Fingerprint        string                 `json:"fingerprint"`
	TraceID            string                 `json:"trace_id"`
	SpanID             string                 `json:"span_id"`
	ServiceName        string                 `json:"service_name"`
	SeverityText       string                 `json:"severity_text"`
	ExternalTracker    ExternalTrackerSummary `json:"external_tracker"`
}

type RollbackRecord struct {
	SchemaVersion         string   `json:"schema_version"`
	CreatedAt             string   `json:"created_at,omitempty"`
	PackageID             string   `json:"package_id"`
	Profile               string   `json:"profile,omitempty"`
	Status                string   `json:"status"`
	Reason                string   `json:"reason"`
	RolledBackCandidateID string   `json:"rolled_back_candidate_id"`
	RestoredCandidateID   string   `json:"restored_candidate_id"`
	TriggeredBy           []string `json:"triggered_by,omitempty"`
}

type RollbackState struct {
	SchemaVersion  string         `json:"schema_version"`
	UpdatedAt      string         `json:"updated_at,omitempty"`
	LatestRollback RollbackRecord `json:"latest_rollback"`
}

type RollbackSummary struct {
	Path                  string   `json:"path"`
	SchemaVersion         string   `json:"schema_version"`
	RecordSchemaVersion   string   `json:"record_schema_version"`
	Status                string   `json:"status"`
	PackageID             string   `json:"package_id"`
	RestoredCandidateID   string   `json:"restored_candidate_id"`
	RolledBackCandidateID string   `json:"rolled_back_candidate_id"`
	TriggeredBy           []string `json:"triggered_by"`
}

type IncidentSummary struct {
	ID                 string   `json:"id"`
	Title              string   `json:"title"`
	Severity           string   `json:"severity"`
	Status             string   `json:"status"`
	Workload           string   `json:"workload"`
	Owner              string   `json:"owner"`
	Source             string   `json:"source"`
	CreatedAt          string   `json:"created_at"`
	ResolvedAt         string   `json:"resolved_at"`
	ErrorFingerprint   string   `json:"error_fingerprint"`
	ImpactedComponents []string `json:"impacted_components"`
	RollbackRequired   bool     `json:"rollback_required"`
	PostmortemPath     string   `json:"postmortem_path"`
}

type TimelineStep struct {
	Order       int      `json:"order"`
	State       string   `json:"state"`
	Status      string   `json:"status"`
	Owner       string   `json:"owner"`
	Evidence    []string `json:"evidence"`
	Description string   `json:"description"`
}

type PostmortemSummary struct {
	Path             string   `json:"path"`
	TemplatePath     string   `json:"template_path"`
	RequiredSections []string `json:"required_sections"`
	ActionItems      int      `json:"action_items"`
	Written          bool     `json:"written"`
}

type ReportSummary struct {
	PassedChecks     int  `json:"passed_checks"`
	FailedChecks     int  `json:"failed_checks"`
	TotalChecks      int  `json:"total_checks"`
	TimelineSteps    int  `json:"timeline_steps"`
	ErrorEvents      int  `json:"error_events"`
	PostmortemReady  bool `json:"postmortem_ready"`
	ExternalTracking bool `json:"external_tracking"`
}

type Report struct {
	SchemaVersion   string               `json:"schema_version"`
	GeneratedAt     string               `json:"generated_at"`
	Passed          bool                 `json:"passed"`
	ProductionReady bool                 `json:"production_ready"`
	CoverageLevel   string               `json:"coverage_level"`
	Incident        IncidentSummary      `json:"incident"`
	Alertmanager    AlertSummary         `json:"alertmanager"`
	ErrorTracking   ErrorTrackingSummary `json:"error_tracking"`
	Rollback        RollbackSummary      `json:"rollback"`
	Postmortem      PostmortemSummary    `json:"postmortem"`
	Timeline        []TimelineStep       `json:"timeline"`
	Checks          []Check              `json:"checks"`
	Evidence        []EvidenceRef        `json:"evidence"`
	Research        []ResearchRef        `json:"research"`
	Notes           []string             `json:"notes"`
	Summary         ReportSummary        `json:"summary"`
}
