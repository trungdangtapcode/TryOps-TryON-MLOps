package main

type Config struct {
	Root               string
	Mode               string
	OutputPath         string
	ComposePath        string
	SchedulePath       string
	BackupDir          string
	PostgresDSN        string
	PostgresContainer  string
	PostgresRestoreDB  string
	MinIOContainer     string
	MinIOBucket        string
	MinIORestoreBucket string
	MinIOAccessKey     string
	MinIOSecretKey     string
	Cleanup            bool
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type Summary struct {
	PlanChecks       int   `json:"plan_checks"`
	TotalChecks      int   `json:"total_checks"`
	PassedChecks     int   `json:"passed_checks"`
	LiveDrill        bool  `json:"live_drill"`
	PostgresDumpByte int64 `json:"postgres_dump_bytes"`
	PostgresTables   int   `json:"postgres_restored_tables"`
	MinIOObjects     int   `json:"minio_restored_objects"`
	MinIOBytes       int64 `json:"minio_restored_bytes"`
	CleanupPerformed bool  `json:"cleanup_performed"`
}

type PostgresSummary struct {
	Tool             string           `json:"tool"`
	Container        string           `json:"container"`
	DumpFormat       string           `json:"dump_format"`
	SourceDSNSet     bool             `json:"source_dsn_set"`
	SourceDatabase   string           `json:"source_database"`
	RestoreDatabase  string           `json:"restore_database"`
	DumpPath         string           `json:"dump_path"`
	DumpBytes        int64            `json:"dump_bytes"`
	RequiredTables   []string         `json:"required_tables"`
	RestoredTables   []string         `json:"restored_tables"`
	SourceRowCounts  map[string]int64 `json:"source_row_counts,omitempty"`
	RestoreRowCounts map[string]int64 `json:"restore_row_counts,omitempty"`
	CleanedUp        bool             `json:"cleaned_up"`
}

type MinIOSummary struct {
	Tool           string `json:"tool"`
	Container      string `json:"container"`
	SourceBucket   string `json:"source_bucket"`
	RestoreBucket  string `json:"restore_bucket"`
	ObjectKey      string `json:"object_key"`
	RestoredKey    string `json:"restored_key"`
	BackupPath     string `json:"backup_path"`
	ObjectBytes    int64  `json:"object_bytes"`
	RestoredObject bool   `json:"restored_object"`
	CleanedUp      bool   `json:"cleaned_up"`
}

type ResearchSource struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type Report struct {
	SchemaVersion string           `json:"schema_version"`
	GeneratedAt   string           `json:"generated_at"`
	Passed        bool             `json:"passed"`
	CoverageLevel string           `json:"coverage_level"`
	Mode          string           `json:"mode"`
	Summary       Summary          `json:"summary"`
	Postgres      PostgresSummary  `json:"postgres"`
	MinIO         MinIOSummary     `json:"minio"`
	Checks        []Check          `json:"checks"`
	Research      []ResearchSource `json:"research"`
	Notes         []string         `json:"notes"`
}
