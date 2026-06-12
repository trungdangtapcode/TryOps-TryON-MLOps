package main

const schemaVersion = "tryops.live_supply_chain.v1"

type Config struct {
	RootPath          string
	OutputPath        string
	SyftSBOMPath      string
	SyftVersionPath   string
	TrivyReportPath   string
	TrivyVersionPath  string
	CosignVersionPath string
	CosignPublicKey   string
	CosignSignature   string
	CosignVerifyPath  string
	SignedBlobPath    string
	SyftImage         string
	TrivyImage        string
	CosignImage       string
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type ToolEvidence struct {
	Name              string `json:"name"`
	Image             string `json:"image"`
	VersionOutputPath string `json:"version_output_path"`
	Version           string `json:"version"`
	Executed          bool   `json:"executed"`
}

type SyftSummary struct {
	Path         string `json:"path"`
	SPDX         string `json:"spdx_version"`
	PackageCount int    `json:"package_count"`
	DocumentName string `json:"document_name"`
}

type TrivySummary struct {
	Path                          string         `json:"path"`
	SchemaVersion                 int            `json:"schema_version"`
	Results                       int            `json:"results"`
	HighCriticalVulnerabilities   int            `json:"high_critical_vulnerabilities"`
	HighCriticalMisconfigurations int            `json:"high_critical_misconfigurations"`
	HighCriticalSecrets           int            `json:"high_critical_secrets"`
	TotalHighCritical             int            `json:"total_high_critical"`
	BySeverity                    map[string]int `json:"by_severity"`
}

type CosignSummary struct {
	SignedBlobPath   string `json:"signed_blob_path"`
	PublicKeyPath    string `json:"public_key_path"`
	SignaturePath    string `json:"signature_path"`
	VerifyOutputPath string `json:"verify_output_path"`
	PublicKeyBytes   int64  `json:"public_key_bytes"`
	SignatureBytes   int64  `json:"signature_bytes"`
	Verified         bool   `json:"verified"`
	TLogSkipped      bool   `json:"tlog_skipped"`
}

type ResearchRef struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type Report struct {
	SchemaVersion   string         `json:"schema_version"`
	GeneratedAt     string         `json:"generated_at"`
	Passed          bool           `json:"passed"`
	ProductionReady bool           `json:"production_ready"`
	CoverageLevel   string         `json:"coverage_level"`
	Tools           []ToolEvidence `json:"tools"`
	Syft            SyftSummary    `json:"syft"`
	Trivy           TrivySummary   `json:"trivy"`
	Cosign          CosignSummary  `json:"cosign"`
	Checks          []Check        `json:"checks"`
	Research        []ResearchRef  `json:"research"`
	Notes           []string       `json:"notes"`
}
