package main

type Event struct {
	SpecVersion     string                 `json:"specversion"`
	ID              string                 `json:"id"`
	Source          string                 `json:"source"`
	Type            string                 `json:"type"`
	Subject         string                 `json:"subject,omitempty"`
	Time            string                 `json:"time"`
	DataContentType string                 `json:"datacontenttype"`
	TenantID        string                 `json:"tenant_id,omitempty"`
	Actor           string                 `json:"actor,omitempty"`
	Data            map[string]interface{} `json:"data"`
}

type auditRecord struct {
	SchemaVersion string                 `json:"schema_version"`
	EventID       string                 `json:"event_id"`
	Type          string                 `json:"type"`
	Subject       string                 `json:"subject,omitempty"`
	Source        string                 `json:"source"`
	Time          string                 `json:"time"`
	TenantID      string                 `json:"tenant_id,omitempty"`
	Actor         string                 `json:"actor,omitempty"`
	Data          map[string]interface{} `json:"data"`
}

type eventResult struct {
	EventID       string   `json:"event_id"`
	Type          string   `json:"type"`
	Subject       string   `json:"subject,omitempty"`
	AuditWritten  bool     `json:"audit_written"`
	WebhookSent   bool     `json:"webhook_sent"`
	WebhookStatus int      `json:"webhook_status,omitempty"`
	Attempts      int      `json:"attempts,omitempty"`
	Errors        []string `json:"errors,omitempty"`
}

type receiverSummary struct {
	Enabled        bool `json:"enabled"`
	AcceptedEvents int  `json:"accepted_events"`
	RejectedEvents int  `json:"rejected_events"`
}

type reportSummary struct {
	Events           int `json:"events"`
	AuditWritten     int `json:"audit_written"`
	WebhookDelivered int `json:"webhook_delivered"`
	Failed           int `json:"failed"`
}

type dispatchReport struct {
	SchemaVersion string          `json:"schema_version"`
	GeneratedAt   string          `json:"generated_at"`
	Mode          string          `json:"mode"`
	Passed        bool            `json:"passed"`
	Summary       reportSummary   `json:"summary"`
	Receiver      receiverSummary `json:"receiver,omitempty"`
	Results       []eventResult   `json:"results"`
}
