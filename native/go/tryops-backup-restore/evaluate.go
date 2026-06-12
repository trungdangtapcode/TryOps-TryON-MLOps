package main

import (
	"context"
	"os"
	"strings"
	"time"
)

func evaluate(ctx context.Context, cfg Config) Report {
	var checks []Check
	runID := time.Now().UTC().Format("20060102T150405Z")
	planChecksBefore := len(checks)
	validatePlanInputs(cfg, &checks)
	postgres := postgresPlan(cfg, &checks)
	minio := minioPlan(cfg, &checks)
	planCheckCount := len(checks) - planChecksBefore
	live := cfg.Mode == "live" || cfg.Mode == "apply"
	if live {
		postgres = runPostgresLive(ctx, cfg, runID, &checks)
		minio = runMinIOLive(ctx, cfg, runID, &checks)
	}
	coverage := "native_backup_restore_plan_contract"
	if live {
		coverage = "native_backup_restore_live_drill"
	}
	report := Report{
		SchemaVersion: "tryops.native_backup_restore_drill.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        allPassed(checks),
		CoverageLevel: coverage,
		Mode:          cfg.Mode,
		Summary: Summary{
			PlanChecks:       planCheckCount,
			TotalChecks:      len(checks),
			PassedChecks:     countPassed(checks),
			LiveDrill:        live,
			PostgresDumpByte: postgres.DumpBytes,
			PostgresTables:   len(postgres.RestoredTables),
			MinIOObjects:     boolToInt(minio.RestoredObject),
			MinIOBytes:       minio.ObjectBytes,
			CleanupPerformed: postgres.CleanedUp && minio.CleanedUp,
		},
		Postgres: postgres,
		MinIO:    minio,
		Checks:   checks,
		Research: []ResearchSource{
			{Name: "PostgreSQL pg_dump", URL: "https://www.postgresql.org/docs/current/app-pgdump.html", Use: "custom-format logical database backup"},
			{Name: "PostgreSQL pg_restore", URL: "https://www.postgresql.org/docs/current/app-pgrestore.html", Use: "isolated restore database drill"},
			{Name: "PostgreSQL backup strategy", URL: "https://www.postgresql.org/docs/current/backup.html", Use: "backup/restore tradeoff model for production profile"},
			{Name: "MinIO mc mirror", URL: "https://min.io/docs/minio/linux/reference/minio-mc/mc-mirror.html", Use: "object-store backup and restore drill"},
		},
		Notes: []string{
			"Plan mode validates Compose storage, schedule wiring, restore isolation, and required open-source tools.",
			"Live mode dumps Postgres in custom format, restores into an isolated temporary database, mirrors a MinIO object through a backup path, and cleans temporary restore targets by default.",
		},
	}
	return report
}

func validatePlanInputs(cfg Config, checks *[]Check) {
	compose, err := loadCompose(cfg.ComposePath)
	if err != nil {
		addCheck(checks, "compose.read", false, err.Error())
	} else {
		addCheck(checks, "compose.read", true, cfg.ComposePath)
		postgres, postgresOK := compose.Services["postgres"]
		minio, minioOK := compose.Services["minio"]
		_, postgresVolumeOK := compose.Volumes["postgres-data"]
		_, minioVolumeOK := compose.Volumes["minio-data"]
		_, postgresSecretOK := compose.Secrets["tryops_postgres_password"]
		_, minioUserSecretOK := compose.Secrets["tryops_minio_root_user"]
		_, minioPasswordSecretOK := compose.Secrets["tryops_minio_root_password"]
		addCheck(checks, "compose.service.postgres", postgresOK, "postgres service")
		addCheck(checks, "compose.service.minio", minioOK, "minio service")
		addCheck(checks, "compose.volume.postgres_data", postgresVolumeOK, "postgres-data volume")
		addCheck(checks, "compose.volume.minio_data", minioVolumeOK, "minio-data volume")
		addCheck(checks, "compose.postgres.mounts_volume", postgresOK && serviceUsesVolume(postgres, "postgres-data"), "postgres-data mounted")
		addCheck(checks, "compose.minio.mounts_volume", minioOK && serviceUsesVolume(minio, "minio-data"), "minio-data mounted")
		addCheck(checks, "compose.postgres.secret", postgresOK && postgresSecretOK && serviceUsesSecret(postgres, "tryops_postgres_password"), "postgres password secret")
		addCheck(checks, "compose.minio.secrets", minioOK && minioUserSecretOK && minioPasswordSecretOK && serviceUsesSecret(minio, "tryops_minio_root_user") && serviceUsesSecret(minio, "tryops_minio_root_password"), "minio root secrets")
	}
	scheduleBody, err := os.ReadFile(cfg.SchedulePath)
	if err != nil {
		addCheck(checks, "restore_drill.schedule.read", false, err.Error())
	} else {
		body := string(scheduleBody)
		addCheck(checks, "restore_drill.schedule.read", true, cfg.SchedulePath)
		addCheck(checks, "restore_drill.schedule.daily", strings.Contains(body, "* * *") && strings.Contains(body, "make native-backup-restore-live"), "daily cron invokes live drill target")
		addCheck(checks, "restore_drill.schedule.logs", strings.Contains(body, "restore-drill.log"), "logs restore drill output")
	}
	addCheck(checks, "backup.dir.configured", cfg.BackupDir != "", cfg.BackupDir)
}

func boolToInt(value bool) int {
	if value {
		return 1
	}
	return 0
}
