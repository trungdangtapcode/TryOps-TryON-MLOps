package main

const schemaVersion = "tryops.native_secret_rotation_contract.v1"

type Config struct {
	RootPath       string
	PolicyPath     string
	ComposePath    string
	EnvExamplePath string
	OutputPath     string
}

type Policy struct {
	SchemaVersion     string           `json:"schema_version"`
	Description       string           `json:"description"`
	Provider          ProviderPolicy   `json:"provider"`
	WorkloadIdentity  WorkloadIdentity `json:"workload_identity"`
	APIKeyRegistry    APIKeyPolicy     `json:"api_key_registry"`
	ManagedSecrets    []ManagedSecret  `json:"managed_secrets"`
	RequiredManifests []string         `json:"required_manifests"`
}

type ProviderPolicy struct {
	Type                 string `json:"type"`
	KVMount              string `json:"kv_mount"`
	KubernetesAuthMount  string `json:"kubernetes_auth_mount"`
	Role                 string `json:"role"`
	ExternalSecretsStore string `json:"external_secrets_store"`
}

type WorkloadIdentity struct {
	ServiceAccount                  string `json:"service_account"`
	Namespace                       string `json:"namespace"`
	ProjectedTokenAudience          string `json:"projected_token_audience"`
	ProjectedTokenExpirationSeconds int    `json:"projected_token_expiration_seconds"`
	SPIFFEID                        string `json:"spiffe_id"`
}

type APIKeyPolicy struct {
	Path                  string `json:"path"`
	Storage               string `json:"storage"`
	RotationDays          int    `json:"rotation_days"`
	OverlapDays           int    `json:"overlap_days"`
	BreakGlassKeyCountMax int    `json:"break_glass_key_count_max"`
}

type ManagedSecret struct {
	Name          string `json:"name"`
	Env           string `json:"env"`
	ComposeSecret string `json:"compose_secret"`
	VaultPath     string `json:"vault_path"`
	VaultProperty string `json:"vault_property"`
	RotationDays  int    `json:"rotation_days"`
	Owner         string `json:"owner"`
}

type APIKeyRegistry struct {
	SchemaVersion string        `json:"schema_version"`
	Keys          []APIKeyEntry `json:"keys"`
}

type APIKeyEntry struct {
	KeyID         string   `json:"key_id"`
	Role          string   `json:"role"`
	KeyHashSHA256 string   `json:"key_hash_sha256"`
	Scopes        []string `json:"scopes"`
	Active        bool     `json:"active"`
}

type ComposeFile struct {
	Secrets  map[string]ComposeSecret  `yaml:"secrets"`
	Services map[string]ComposeService `yaml:"services"`
}

type ComposeSecret struct {
	Environment string `yaml:"environment"`
	File        string `yaml:"file"`
}

type ComposeService struct {
	Secrets     []string          `yaml:"secrets"`
	Environment map[string]string `yaml:"environment"`
}

type KubernetesDoc struct {
	APIVersion                   string                 `yaml:"apiVersion"`
	Kind                         string                 `yaml:"kind"`
	Metadata                     map[string]interface{} `yaml:"metadata"`
	Spec                         map[string]interface{} `yaml:"spec"`
	AutomountServiceAccountToken *bool                  `yaml:"automountServiceAccountToken"`
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type ResearchRef struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type EvidenceRef struct {
	Name          string `json:"name"`
	Path          string `json:"path"`
	SchemaVersion string `json:"schema_version,omitempty"`
	Status        string `json:"status"`
	Detail        string `json:"detail,omitempty"`
}

type ProviderSummary struct {
	Type                 string `json:"type"`
	KVMount              string `json:"kv_mount"`
	KubernetesAuthMount  string `json:"kubernetes_auth_mount"`
	Role                 string `json:"role"`
	ExternalSecretsStore string `json:"external_secrets_store"`
}

type WorkloadIdentitySummary struct {
	ServiceAccount                  string `json:"service_account"`
	Namespace                       string `json:"namespace"`
	ProjectedTokenAudience          string `json:"projected_token_audience"`
	ProjectedTokenExpirationSeconds int    `json:"projected_token_expiration_seconds"`
	SPIFFEID                        string `json:"spiffe_id"`
	ProjectedTokenManifest          bool   `json:"projected_token_manifest"`
}

type APIKeyRegistrySummary struct {
	Path                  string   `json:"path"`
	Storage               string   `json:"storage"`
	RotationDays          int      `json:"rotation_days"`
	OverlapDays           int      `json:"overlap_days"`
	ActiveKeys            int      `json:"active_keys"`
	Roles                 []string `json:"roles"`
	HashOnly              bool     `json:"hash_only"`
	BreakGlassKeyCountMax int      `json:"break_glass_key_count_max"`
}

type SecretSummary struct {
	Name           string `json:"name"`
	Env            string `json:"env"`
	ComposeSecret  string `json:"compose_secret,omitempty"`
	VaultPath      string `json:"vault_path"`
	VaultProperty  string `json:"vault_property"`
	RotationDays   int    `json:"rotation_days"`
	Owner          string `json:"owner"`
	ComposePresent bool   `json:"compose_present"`
	ExternalSecret bool   `json:"external_secret"`
}

type LiveReadiness struct {
	VaultAddrConfigured bool   `json:"vault_addr_configured"`
	TokenPathConfigured bool   `json:"token_path_configured"`
	Mode                string `json:"mode"`
}

type ReportSummary struct {
	PassedChecks    int `json:"passed_checks"`
	FailedChecks    int `json:"failed_checks"`
	TotalChecks     int `json:"total_checks"`
	ManagedSecrets  int `json:"managed_secrets"`
	ComposeSecrets  int `json:"compose_secrets"`
	ExternalSecrets int `json:"external_secrets"`
	RotationMaxDays int `json:"rotation_max_days"`
}

type Report struct {
	SchemaVersion    string                  `json:"schema_version"`
	GeneratedAt      string                  `json:"generated_at"`
	Passed           bool                    `json:"passed"`
	ProductionReady  bool                    `json:"production_ready"`
	CoverageLevel    string                  `json:"coverage_level"`
	PolicyPath       string                  `json:"policy_path"`
	ComposePath      string                  `json:"compose_path"`
	EnvExamplePath   string                  `json:"env_example_path"`
	Provider         ProviderSummary         `json:"provider"`
	WorkloadIdentity WorkloadIdentitySummary `json:"workload_identity"`
	APIKeyRegistry   APIKeyRegistrySummary   `json:"api_key_registry"`
	Secrets          []SecretSummary         `json:"secrets"`
	LiveReadiness    LiveReadiness           `json:"live_readiness"`
	Checks           []Check                 `json:"checks"`
	Evidence         []EvidenceRef           `json:"evidence"`
	Research         []ResearchRef           `json:"research"`
	Notes            []string                `json:"notes"`
	Summary          ReportSummary           `json:"summary"`
}
