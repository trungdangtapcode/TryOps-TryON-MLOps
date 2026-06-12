package main

type QuotaRequest struct {
	UserID          string `json:"user_id"`
	Plan            string `json:"plan"`
	Workload        string `json:"workload"`
	RequestUnits    int    `json:"request_units"`
	EstimatedTokens int    `json:"estimated_tokens"`
	Period          string `json:"period"`
}

type QuotaDecision struct {
	SchemaVersion string                 `json:"schema_version"`
	Allowed       bool                   `json:"allowed"`
	Reason        string                 `json:"reason"`
	Checks        []QuotaDimensionResult `json:"checks"`
}

type QuotaDimensionResult struct {
	Dimension      string `json:"dimension"`
	Limit          int    `json:"limit"`
	Used           int    `json:"used"`
	Increment      int    `json:"increment"`
	RemainingAfter int    `json:"remaining_after"`
	Allowed        bool   `json:"allowed"`
	UsedAfter      int    `json:"used_after"`
}

type Attempt struct {
	Index      int    `json:"index"`
	GatewayURL string `json:"gateway_url"`
	StatusCode int    `json:"status_code"`
	Allowed    bool   `json:"allowed"`
	Reason     string `json:"reason,omitempty"`
	Error      string `json:"error,omitempty"`
}

type Report struct {
	SchemaVersion string          `json:"schema_version"`
	GeneratedAt   string          `json:"generated_at"`
	Passed        bool            `json:"passed"`
	CoverageLevel string          `json:"coverage_level"`
	Research      []ResearchLink  `json:"research"`
	Config        ReportConfig    `json:"config"`
	Summary       ReportSummary   `json:"summary"`
	Checks        map[string]bool `json:"checks"`
	Attempts      []Attempt       `json:"attempts"`
}

type ResearchLink struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type ReportConfig struct {
	GatewayURLs     []string `json:"gateway_urls"`
	Requests        int      `json:"requests"`
	ExpectedAllowed int      `json:"expected_allowed"`
	Concurrency     int      `json:"concurrency"`
	Plan            string   `json:"plan"`
	Workload        string   `json:"workload"`
	Period          string   `json:"period"`
}

type ReportSummary struct {
	Gateways      int `json:"gateways"`
	Requests      int `json:"requests"`
	Allowed       int `json:"allowed"`
	Rejected      int `json:"rejected"`
	Errors        int `json:"errors"`
	ExpectedAllow int `json:"expected_allowed"`
}
