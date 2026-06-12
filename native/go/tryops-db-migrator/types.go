package main

type Config struct {
	Root          string
	MigrationsDir string
	OutputPath    string
	DSN           string
	Mode          string
	MinConns      int32
	MaxConns      int32
}

type Migration struct {
	Version  string
	Name     string
	Path     string
	Checksum string
	SQL      string
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type MigrationSummary struct {
	Version  string `json:"version"`
	Name     string `json:"name"`
	Path     string `json:"path"`
	Checksum string `json:"checksum_sha256"`
	Applied  bool   `json:"applied"`
}

type PoolSummary struct {
	Driver            string `json:"driver"`
	MinConns          int32  `json:"min_conns"`
	MaxConns          int32  `json:"max_conns"`
	Configured        bool   `json:"configured"`
	LivePing          bool   `json:"live_ping"`
	ConnectionAcquire bool   `json:"connection_acquire"`
}

type Summary struct {
	TotalMigrations   int   `json:"total_migrations"`
	AppliedMigrations int   `json:"applied_migrations"`
	RequiredTables    int   `json:"required_tables"`
	PassedChecks      int   `json:"passed_checks"`
	TotalChecks       int   `json:"total_checks"`
	PoolMaxConns      int32 `json:"pool_max_conns"`
	LiveApply         bool  `json:"live_apply"`
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
	Pool          PoolSummary        `json:"pool"`
	Migrations    []MigrationSummary `json:"migrations"`
	Checks        []Check            `json:"checks"`
	Research      []ResearchSource   `json:"research"`
	Notes         []string           `json:"notes"`
}
