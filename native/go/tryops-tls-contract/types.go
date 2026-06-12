package main

type Config struct {
	Root        string
	ComposePath string
	OutputPath  string
	CertPath    string
	KeyPath     string
	Mode        string
	URL         string
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type Summary struct {
	PassedChecks      int  `json:"passed_checks"`
	TotalChecks       int  `json:"total_checks"`
	LiveHandshake     bool `json:"live_handshake"`
	ComposeTLSProfile bool `json:"compose_tls_profile"`
	CertDaysRemaining int  `json:"cert_days_remaining"`
	HTTPSHealth       bool `json:"https_health"`
	PlainHTTPRejected bool `json:"plain_http_rejected"`
}

type ComposeSummary struct {
	Service            string   `json:"service"`
	Profile            string   `json:"profile"`
	PortVariable       string   `json:"port_variable"`
	TLSCertSecret      string   `json:"tls_cert_secret"`
	TLSKeySecret       string   `json:"tls_key_secret"`
	HealthcheckScheme  string   `json:"healthcheck_scheme"`
	RequiredEnv        []string `json:"required_env"`
	RequiredSecretRefs []string `json:"required_secret_refs"`
}

type CertificateSummary struct {
	Path          string   `json:"path"`
	KeyPath       string   `json:"key_path"`
	Subject       string   `json:"subject"`
	DNSNames      []string `json:"dns_names"`
	IPAddresses   []string `json:"ip_addresses"`
	NotBefore     string   `json:"not_before"`
	NotAfter      string   `json:"not_after"`
	DaysRemaining int      `json:"days_remaining"`
	KeyPairLoads  bool     `json:"key_pair_loads"`
}

type LiveSummary struct {
	URL              string `json:"url"`
	TLSVersion       string `json:"tls_version"`
	CipherSuite      string `json:"cipher_suite"`
	PeerCertificates int    `json:"peer_certificates"`
	HealthStatusCode int    `json:"health_status_code"`
	HealthBody       string `json:"health_body"`
	PlainHTTPError   string `json:"plain_http_error"`
}

type ResearchSource struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type Report struct {
	SchemaVersion string             `json:"schema_version"`
	GeneratedAt   string             `json:"generated_at"`
	Passed        bool               `json:"passed"`
	CoverageLevel string             `json:"coverage_level"`
	Mode          string             `json:"mode"`
	Summary       Summary            `json:"summary"`
	Compose       ComposeSummary     `json:"compose"`
	Certificate   CertificateSummary `json:"certificate"`
	Live          LiveSummary        `json:"live,omitempty"`
	Checks        []Check            `json:"checks"`
	Research      []ResearchSource   `json:"research"`
	Notes         []string           `json:"notes"`
}
