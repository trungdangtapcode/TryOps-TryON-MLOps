package main

const EnvelopeSchema = "tryops.native_trace_log_envelope.v1"
const ReportSchema = "tryops.native_trace_envelope.v1"

type Envelope struct {
	SchemaVersion     string                 `json:"schema_version"`
	Timestamp         string                 `json:"timestamp"`
	ObservedTimestamp string                 `json:"observed_timestamp"`
	Language          string                 `json:"language"`
	Runtime           string                 `json:"runtime"`
	Component         string                 `json:"component"`
	EventName         string                 `json:"event_name"`
	SeverityText      string                 `json:"severity_text"`
	SeverityNumber    int                    `json:"severity_number"`
	TraceID           string                 `json:"trace_id"`
	SpanID            string                 `json:"span_id"`
	TraceFlags        string                 `json:"trace_flags"`
	Traceparent       string                 `json:"traceparent"`
	RequestID         string                 `json:"request_id"`
	Workload          string                 `json:"workload"`
	Resource          map[string]string      `json:"resource"`
	Attributes        map[string]interface{} `json:"attributes"`
}

type Validation struct {
	Language  string   `json:"language"`
	Runtime   string   `json:"runtime"`
	RequestID string   `json:"request_id"`
	Passed    bool     `json:"passed"`
	Errors    []string `json:"errors,omitempty"`
}

type Summary struct {
	TotalEnvelopes  int            `json:"total_envelopes"`
	PassedEnvelopes int            `json:"passed_envelopes"`
	FailedEnvelopes int            `json:"failed_envelopes"`
	ByLanguage      map[string]int `json:"by_language"`
	RequiredCovered bool           `json:"required_languages_covered"`
}

type Source struct {
	Name    string `json:"name"`
	Path    string `json:"path,omitempty"`
	Present bool   `json:"present"`
}

type ResearchSource struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type Report struct {
	SchemaVersion string           `json:"schema_version"`
	GeneratedAt   string           `json:"generated_at"`
	Passed        bool             `json:"passed"`
	CoverageLevel string           `json:"coverage_level"`
	Contract      string           `json:"contract"`
	Research      []ResearchSource `json:"research"`
	Sources       []Source         `json:"sources"`
	Summary       Summary          `json:"summary"`
	Validations   []Validation     `json:"validations"`
	Envelopes     []Envelope       `json:"envelopes"`
}
