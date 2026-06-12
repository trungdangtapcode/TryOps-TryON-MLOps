package main

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
)

func parseConfig() Config {
	root := flag.String("root", getenv("TRYOPS_ROOT", "."), "repository root")
	mode := flag.String("mode", getenv("TRYOPS_BACKUP_RESTORE_MODE", "plan"), "plan or live")
	output := flag.String("output", getenv("TRYOPS_BACKUP_RESTORE_OUTPUT", "artifacts/eval/backup/native_backup_restore_drill.json"), "report output path")
	compose := flag.String("compose", getenv("TRYOPS_COMPOSE_FILE", "docker-compose.yml"), "docker compose file")
	schedule := flag.String("schedule", getenv("TRYOPS_RESTORE_DRILL_SCHEDULE", "infra/backup/restore_drill.cron"), "restore drill schedule file")
	backupDir := flag.String("backup-dir", getenv("TRYOPS_BACKUP_DIR", "artifacts/backups/native_restore_drill"), "backup artifact directory")
	postgresDSN := flag.String("postgres-dsn", firstEnv("TRYOPS_POSTGRES_BACKUP_DSN", "TRYOPS_POSTGRES_MIGRATION_DSN", "TRYOPS_DATABASE_URL"), "Postgres DSN for live backup/restore drill")
	postgresContainer := flag.String("postgres-container", getenv("TRYOPS_POSTGRES_CONTAINER", "flow-postgres-1"), "Postgres container name for matching pg_dump/pg_restore tools")
	restoreDB := flag.String("postgres-restore-db", getenv("TRYOPS_POSTGRES_RESTORE_DB", "tryops_restore_drill"), "temporary restore database name")
	minioContainer := flag.String("minio-container", getenv("TRYOPS_MINIO_CONTAINER", "flow-minio-1"), "MinIO container name for mc commands")
	minioBucket := flag.String("minio-bucket", getenv("TRYOPS_MINIO_BUCKET", "tryops-artifacts"), "source MinIO bucket")
	minioRestoreBucket := flag.String("minio-restore-bucket", getenv("TRYOPS_MINIO_RESTORE_BUCKET", "tryops-restore-drill"), "restore-drill MinIO bucket")
	minioAccessKey := flag.String("minio-access-key", getenv("TRYOPS_MINIO_ROOT_USER", ""), "MinIO root access key; defaults to container env in live mode")
	minioSecretKey := flag.String("minio-secret-key", getenv("TRYOPS_MINIO_ROOT_PASSWORD", ""), "MinIO root secret key; defaults to container env in live mode")
	cleanup := flag.Bool("cleanup", envBool("TRYOPS_BACKUP_RESTORE_CLEANUP", true), "clean temporary restore targets")
	flag.Parse()

	cfg := Config{
		Root:               filepath.Clean(*root),
		Mode:               strings.ToLower(strings.TrimSpace(*mode)),
		OutputPath:         *output,
		ComposePath:        *compose,
		SchedulePath:       *schedule,
		BackupDir:          *backupDir,
		PostgresDSN:        strings.TrimSpace(*postgresDSN),
		PostgresContainer:  strings.TrimSpace(*postgresContainer),
		PostgresRestoreDB:  sanitizeIdentifier(*restoreDB),
		MinIOContainer:     strings.TrimSpace(*minioContainer),
		MinIOBucket:        strings.Trim(strings.TrimSpace(*minioBucket), "/"),
		MinIORestoreBucket: strings.Trim(strings.TrimSpace(*minioRestoreBucket), "/"),
		MinIOAccessKey:     strings.TrimSpace(*minioAccessKey),
		MinIOSecretKey:     strings.TrimSpace(*minioSecretKey),
		Cleanup:            *cleanup,
	}
	cfg.OutputPath = rootRelative(cfg.Root, cfg.OutputPath)
	cfg.ComposePath = rootRelative(cfg.Root, cfg.ComposePath)
	cfg.SchedulePath = rootRelative(cfg.Root, cfg.SchedulePath)
	cfg.BackupDir = rootRelative(cfg.Root, cfg.BackupDir)
	return cfg
}

func rootRelative(root string, path string) string {
	if filepath.IsAbs(path) {
		return filepath.Clean(path)
	}
	return filepath.Join(root, path)
}

func getenv(name string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	return value
}

func firstEnv(names ...string) string {
	for _, name := range names {
		if value := strings.TrimSpace(os.Getenv(name)); value != "" {
			return value
		}
	}
	return ""
}

func envBool(name string, fallback bool) bool {
	value := strings.ToLower(strings.TrimSpace(os.Getenv(name)))
	switch value {
	case "1", "true", "yes", "y":
		return true
	case "0", "false", "no", "n":
		return false
	default:
		return fallback
	}
}
