package main

type NativePolicyCandidate struct {
	CandidateID     string                 `json:"candidate_id"`
	Workload        string                 `json:"workload"`
	ModelName       string                 `json:"model_name"`
	ModelVersion    string                 `json:"model_version"`
	Metrics         map[string]float64     `json:"metrics"`
	Artifacts       map[string]string      `json:"artifacts"`
	Approvals       []string               `json:"approvals"`
	RiskStatus      string                 `json:"risk_status"`
	Vulnerabilities map[string]int         `json:"vulnerabilities"`
	Signed          bool                   `json:"signed"`
	Metadata        map[string]interface{} `json:"metadata"`
}

type NativePolicyDecision struct {
	Approved    bool     `json:"approved"`
	TargetStage string   `json:"target_stage"`
	Reasons     []string `json:"reasons"`
}

type NativePolicyResult struct {
	Available  bool                 `json:"available"`
	CLIPath    string               `json:"cli_path,omitempty"`
	ReturnCode int                  `json:"returncode,omitempty"`
	WireFormat string               `json:"wire_format,omitempty"`
	Decision   NativePolicyDecision `json:"decision"`
	Error      string               `json:"error,omitempty"`
}
