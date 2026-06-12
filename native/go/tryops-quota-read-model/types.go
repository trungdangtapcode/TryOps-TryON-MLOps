package main

type QuotaUsageReport struct {
	SchemaVersion string          `json:"schema_version"`
	UserID        string          `json:"user_id,omitempty"`
	Plan          string          `json:"plan,omitempty"`
	NativeQuota   NativeQuotaInfo `json:"native_quota,omitempty"`
	Decisions     []QuotaDecision `json:"decisions"`
	Snapshot      QuotaSnapshot   `json:"snapshot"`
}

type NativeQuotaInfo struct {
	Engine    string `json:"engine"`
	Available bool   `json:"available"`
	Reason    string `json:"reason,omitempty"`
}

type QuotaDecision struct {
	Allowed  bool                   `json:"allowed"`
	Period   string                 `json:"period"`
	UserHash string                 `json:"user_hash"`
	Plan     string                 `json:"plan"`
	Workload string                 `json:"workload"`
	Checks   []QuotaDimensionCheck  `json:"checks"`
	Raw      map[string]interface{} `json:"-"`
}

type QuotaDimensionCheck struct {
	Dimension      string `json:"dimension"`
	Limit          uint64 `json:"limit"`
	Used           uint64 `json:"used"`
	Increment      uint64 `json:"increment"`
	RemainingAfter uint64 `json:"remaining_after"`
	Allowed        bool   `json:"allowed"`
}

type QuotaSnapshot struct {
	SchemaVersion string          `json:"schema_version"`
	Engine        string          `json:"engine,omitempty"`
	Usage         []QuotaUsageRow `json:"usage"`
	Tenants       []TenantSource  `json:"tenants,omitempty"`
}

type TenantSource struct {
	Period     string `json:"period"`
	UserHash   string `json:"user_hash"`
	TotalUsed  uint64 `json:"total_used"`
	Dimensions []struct {
		Dimension string `json:"dimension"`
		Used      uint64 `json:"used"`
	} `json:"dimensions"`
}

type QuotaUsageRow struct {
	Period    string `json:"period"`
	UserHash  string `json:"user_hash"`
	Dimension string `json:"dimension"`
	Used      uint64 `json:"used"`
}

type DimensionReadModel struct {
	Dimension      string  `json:"dimension"`
	Used           uint64  `json:"used"`
	Limit          uint64  `json:"limit"`
	Remaining      uint64  `json:"remaining"`
	UtilizationPct float64 `json:"utilization_pct"`
	UnitPriceUSD   float64 `json:"unit_price_usd"`
	ShowbackUSD    float64 `json:"showback_usd"`
}

type TenantReadModel struct {
	Period         string               `json:"period"`
	UserHash       string               `json:"user_hash"`
	Plan           string               `json:"plan"`
	TotalUsed      uint64               `json:"total_used"`
	TotalLimit     uint64               `json:"total_limit"`
	Remaining      uint64               `json:"remaining"`
	UtilizationPct float64              `json:"utilization_pct"`
	ShowbackUSD    float64              `json:"showback_usd"`
	Dimensions     []DimensionReadModel `json:"dimensions"`
	Risk           string               `json:"risk"`
}

type PeriodSummary struct {
	Period      string  `json:"period"`
	Tenants     int     `json:"tenants"`
	TotalUsed   uint64  `json:"total_used"`
	ShowbackUSD float64 `json:"showback_usd"`
}

type Summary struct {
	Tenants       int     `json:"tenants"`
	Periods       int     `json:"periods"`
	Dimensions    int     `json:"dimensions"`
	TotalUsed     uint64  `json:"total_used"`
	TotalLimit    uint64  `json:"total_limit"`
	ShowbackUSD   float64 `json:"showback_usd"`
	NativeSource  bool    `json:"native_source"`
	AtRiskTenants int     `json:"at_risk_tenants"`
}

type ResearchSource struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type Report struct {
	SchemaVersion string            `json:"schema_version"`
	GeneratedAt   string            `json:"generated_at"`
	Passed        bool              `json:"passed"`
	CoverageLevel string            `json:"coverage_level"`
	SourcePath    string            `json:"source_path"`
	SourceEngine  string            `json:"source_engine"`
	Research      []ResearchSource  `json:"research"`
	Summary       Summary           `json:"summary"`
	Periods       []PeriodSummary   `json:"periods"`
	Tenants       []TenantReadModel `json:"tenants"`
	Checks        map[string]bool   `json:"checks"`
	Warnings      []string          `json:"warnings,omitempty"`
}
