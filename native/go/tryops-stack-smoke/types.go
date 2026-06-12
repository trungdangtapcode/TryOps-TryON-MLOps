package main

type smokeCheck struct {
	Name         string
	Method       string
	URL          string
	Body         string
	ContentType  string
	Headers      map[string]string
	WantStatus   int
	WantContains []string
}

type checkResult struct {
	Name       string   `json:"name"`
	URL        string   `json:"url"`
	Method     string   `json:"method"`
	Passed     bool     `json:"passed"`
	StatusCode int      `json:"status_code,omitempty"`
	Attempts   int      `json:"attempts"`
	DurationMS int64    `json:"duration_ms"`
	Error      string   `json:"error,omitempty"`
	Missing    []string `json:"missing,omitempty"`
}

type smokeReport struct {
	SchemaVersion string        `json:"schema_version"`
	GeneratedAt   string        `json:"generated_at"`
	Passed        bool          `json:"passed"`
	Checks        []checkResult `json:"checks"`
}
