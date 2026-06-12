package main

type commandSpec struct {
	Name              string
	Args              []string
	ExpectedExitCodes []int
	WantContains      []string
}

type commandResult struct {
	Name              string   `json:"name"`
	Command           []string `json:"command"`
	Passed            bool     `json:"passed"`
	ExitCode          int      `json:"exit_code"`
	ExpectedExitCodes []int    `json:"expected_exit_codes"`
	DurationMS        int64    `json:"duration_ms"`
	Error             string   `json:"error,omitempty"`
	Missing           []string `json:"missing,omitempty"`
	OutputTail        string   `json:"output_tail,omitempty"`
}

type evidenceResult struct {
	Name    string   `json:"name"`
	Path    string   `json:"path"`
	Passed  bool     `json:"passed"`
	Details []string `json:"details,omitempty"`
	Error   string   `json:"error,omitempty"`
}

type acceptanceReport struct {
	SchemaVersion string           `json:"schema_version"`
	GeneratedAt   string           `json:"generated_at"`
	Passed        bool             `json:"passed"`
	Summary       reportSummary    `json:"summary"`
	Commands      []commandResult  `json:"commands"`
	Evidence      []evidenceResult `json:"evidence"`
}

type reportSummary struct {
	CommandChecks  int `json:"command_checks"`
	EvidenceChecks int `json:"evidence_checks"`
	PassedChecks   int `json:"passed_checks"`
	FailedChecks   int `json:"failed_checks"`
}
