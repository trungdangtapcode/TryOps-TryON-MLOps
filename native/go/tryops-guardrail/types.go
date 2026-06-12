package main

const schemaVersion = "tryops.native_guardrail.v1"

type guardrailRequest struct {
	Prompt           string         `json:"prompt"`
	OutputText       string         `json:"output_text"`
	MaxTokens        int            `json:"max_tokens"`
	Structured       bool           `json:"structured"`
	StructuredAnswer map[string]any `json:"structured_answer"`
}

type finding struct {
	CheckID  string `json:"check_id"`
	OWASPID  string `json:"owasp_id"`
	Risk     string `json:"risk"`
	Stage    string `json:"stage"`
	Action   string `json:"action"`
	Severity string `json:"severity"`
	Message  string `json:"message"`
}

type guardrailResponse struct {
	SchemaVersion string    `json:"schema_version"`
	Engine        engine    `json:"engine"`
	Status        string    `json:"status"`
	Blocked       bool      `json:"blocked"`
	RiskIDs       []string  `json:"risk_ids"`
	Findings      []finding `json:"findings"`
}

type engine struct {
	Name     string `json:"name"`
	Language string `json:"language"`
	Version  string `json:"version"`
}
