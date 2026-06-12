package main

type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
}

type ReconcileRequest struct {
	CandidateID string `json:"candidate_id"`
	Workload    string `json:"workload"`
	TargetStage string `json:"target_stage"`
}

type ReconcileResponse struct {
	Accepted bool     `json:"accepted"`
	Actions  []string `json:"actions"`
}

type RegistryWebhookPayload struct {
	Entity    string                 `json:"entity"`
	Action    string                 `json:"action"`
	Timestamp string                 `json:"timestamp"`
	Workspace string                 `json:"workspace"`
	Data      map[string]interface{} `json:"data"`
}

type RegistryWebhookResponse struct {
	Accepted     bool                `json:"accepted"`
	Event        string              `json:"event"`
	CandidateID  string              `json:"candidate_id"`
	PackageID    string              `json:"package_id"`
	NativePolicy *NativePolicyResult `json:"native_policy,omitempty"`
	Actions      []string            `json:"actions"`
}

type PromotionPRResponse struct {
	Accepted     bool                `json:"accepted"`
	Event        string              `json:"event"`
	PullRequest  int                 `json:"pull_request"`
	CandidateID  string              `json:"candidate_id"`
	PackageID    string              `json:"package_id"`
	TargetStage  string              `json:"target_stage"`
	MergeCommit  string              `json:"merge_commit"`
	Repository   string              `json:"repository"`
	NativePolicy *NativePolicyResult `json:"native_policy,omitempty"`
	Actions      []string            `json:"actions"`
}

type AlertmanagerWebhookPayload struct {
	Receiver     string                 `json:"receiver"`
	Status       string                 `json:"status"`
	Alerts       []AlertmanagerAlert    `json:"alerts"`
	GroupLabels  map[string]string      `json:"groupLabels"`
	CommonLabels map[string]string      `json:"commonLabels"`
	ExternalURL  string                 `json:"externalURL"`
	Version      string                 `json:"version"`
	GroupKey     string                 `json:"groupKey"`
	Truncated    int                    `json:"truncatedAlerts"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

type AlertmanagerAlert struct {
	Status       string            `json:"status"`
	Labels       map[string]string `json:"labels"`
	Annotations  map[string]string `json:"annotations"`
	StartsAt     string            `json:"startsAt"`
	EndsAt       string            `json:"endsAt,omitempty"`
	GeneratorURL string            `json:"generatorURL,omitempty"`
	Fingerprint  string            `json:"fingerprint,omitempty"`
}

type AlertmanagerWebhookResponse struct {
	Accepted   bool     `json:"accepted"`
	Receiver   string   `json:"receiver"`
	Status     string   `json:"status"`
	AlertCount int      `json:"alert_count"`
	Severity   string   `json:"severity"`
	Workload   string   `json:"workload"`
	Actions    []string `json:"actions"`
}
