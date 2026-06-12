package main

import "time"

type jobSpec struct {
	Name        string
	Workload    string
	Method      string
	Path        string
	Payload     map[string]interface{}
	Timeout     time.Duration
	MaxAttempts int
	Retry       retryPolicy
	Poll        *pollSpec
}

type pollSpec struct {
	PathPrefix string
	Timeout    time.Duration
	Interval   time.Duration
}

type retryPolicy struct {
	BaseDelay time.Duration
}

type httpJSONResponse struct {
	StatusCode int
	Body       []byte
	Data       map[string]interface{}
}

type jobResult struct {
	Name       string                 `json:"name"`
	Workload   string                 `json:"workload"`
	Method     string                 `json:"method"`
	Path       string                 `json:"path"`
	Passed     bool                   `json:"passed"`
	Status     string                 `json:"status"`
	Attempts   int                    `json:"attempts"`
	Polls      int                    `json:"polls,omitempty"`
	HTTPStatus int                    `json:"http_status,omitempty"`
	JobID      string                 `json:"job_id,omitempty"`
	RequestID  string                 `json:"request_id,omitempty"`
	DurationMS int64                  `json:"duration_ms"`
	Error      string                 `json:"error,omitempty"`
	Response   map[string]interface{} `json:"response,omitempty"`
}

type reportSummary struct {
	Total  int `json:"total"`
	Passed int `json:"passed"`
	Failed int `json:"failed"`
}

type jobReport struct {
	SchemaVersion string                 `json:"schema_version"`
	GeneratedAt   string                 `json:"generated_at"`
	BaseURL       string                 `json:"base_url"`
	Passed        bool                   `json:"passed"`
	Summary       reportSummary          `json:"summary"`
	Config        map[string]interface{} `json:"config"`
	Jobs          []jobResult            `json:"jobs"`
}
