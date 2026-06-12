package main

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

var requiredPostgresTables = []string{
	"requests",
	"feedback",
	"jobs",
	"models",
	"audit_log",
	"tryops_quota_usage",
	"tryops_schema_migrations",
}

func postgresPlan(cfg Config, checks *[]Check) PostgresSummary {
	conn := postgresConnectionFromDSN(cfg.PostgresDSN)
	summary := PostgresSummary{
		Tool:            "docker exec pg_dump/pg_restore/psql",
		Container:       cfg.PostgresContainer,
		DumpFormat:      "custom",
		SourceDSNSet:    cfg.PostgresDSN != "",
		SourceDatabase:  conn.Database,
		RestoreDatabase: cfg.PostgresRestoreDB,
		RequiredTables:  append([]string{}, requiredPostgresTables...),
	}
	addCheck(checks, "postgres.docker.available", commandAvailable("docker"), "docker on PATH")
	addCheck(checks, "postgres.container.configured", cfg.PostgresContainer != "", cfg.PostgresContainer)
	addCheck(checks, "postgres.restore_db.isolated", cfg.PostgresRestoreDB != "" && !strings.EqualFold(cfg.PostgresRestoreDB, "tryops"), cfg.PostgresRestoreDB)
	return summary
}

func runPostgresLive(ctx context.Context, cfg Config, runID string, checks *[]Check) PostgresSummary {
	summary := postgresPlan(cfg, checks)
	if cfg.PostgresDSN == "" {
		addCheck(checks, "postgres.dsn.present", false, "TRYOPS_POSTGRES_BACKUP_DSN is required for live mode")
		return summary
	}
	addCheck(checks, "postgres.dsn.present", true, "DSN configured")
	conn := postgresConnectionFromDSN(cfg.PostgresDSN)
	summary.SourceDatabase = conn.Database
	if _, _, err := runCommand(ctx, 20*time.Second, "docker", "exec", cfg.PostgresContainer, "sh", "-lc", "command -v pg_dump >/dev/null && command -v pg_restore >/dev/null && command -v psql >/dev/null"); err != nil {
		addCheck(checks, "postgres.container_tools.available", false, err.Error())
		return summary
	}
	addCheck(checks, "postgres.container_tools.available", true, cfg.PostgresContainer)
	if err := os.MkdirAll(cfg.BackupDir, 0o755); err != nil {
		addCheck(checks, "postgres.backup_dir.create", false, err.Error())
		return summary
	}
	addCheck(checks, "postgres.backup_dir.create", true, cfg.BackupDir)

	dumpPath := filepath.Join(cfg.BackupDir, "tryops-postgres-"+runID+".dump")
	containerDumpPath := "/tmp/tryops-postgres-" + runID + ".dump"
	summary.DumpPath = dumpPath
	if _, _, err := runCommand(ctx, 90*time.Second, "docker", "exec", cfg.PostgresContainer, "pg_dump", "-U", conn.User, "-d", conn.Database, "--format=custom", "--no-owner", "--no-privileges", "--file", containerDumpPath); err != nil {
		addCheck(checks, "postgres.pg_dump", false, err.Error())
		return summary
	}
	if _, _, err := runCommand(ctx, 30*time.Second, "docker", "cp", cfg.PostgresContainer+":"+containerDumpPath, dumpPath); err != nil {
		addCheck(checks, "postgres.dump.copy_from_container", false, err.Error())
		return summary
	}
	addCheck(checks, "postgres.pg_dump", true, containerDumpPath)
	addCheck(checks, "postgres.dump.copy_from_container", true, dumpPath)
	if stat, err := os.Stat(dumpPath); err == nil {
		summary.DumpBytes = stat.Size()
		addCheck(checks, "postgres.dump.non_empty", stat.Size() > 0, fmt.Sprintf("%d bytes", stat.Size()))
	} else {
		addCheck(checks, "postgres.dump.non_empty", false, err.Error())
	}

	dropSQL := "DROP DATABASE IF EXISTS " + quoteIdent(cfg.PostgresRestoreDB) + " WITH (FORCE)"
	createSQL := "CREATE DATABASE " + quoteIdent(cfg.PostgresRestoreDB)
	if _, _, err := runCommand(ctx, 30*time.Second, "docker", "exec", cfg.PostgresContainer, "psql", "-U", conn.User, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", dropSQL); err != nil {
		addCheck(checks, "postgres.restore_db.drop_before", false, err.Error())
		return summary
	}
	addCheck(checks, "postgres.restore_db.drop_before", true, cfg.PostgresRestoreDB)
	if _, _, err := runCommand(ctx, 30*time.Second, "docker", "exec", cfg.PostgresContainer, "psql", "-U", conn.User, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", createSQL); err != nil {
		addCheck(checks, "postgres.restore_db.create", false, err.Error())
		return summary
	}
	addCheck(checks, "postgres.restore_db.create", true, cfg.PostgresRestoreDB)

	if _, _, err := runCommand(ctx, 90*time.Second, "docker", "exec", cfg.PostgresContainer, "pg_restore", "-U", conn.User, "-d", cfg.PostgresRestoreDB, "--no-owner", "--no-privileges", containerDumpPath); err != nil {
		addCheck(checks, "postgres.pg_restore", false, err.Error())
		cleanupPostgres(ctx, cfg, conn, containerDumpPath, checks, &summary)
		return summary
	}
	addCheck(checks, "postgres.pg_restore", true, cfg.PostgresRestoreDB)

	sourceCounts := map[string]int64{}
	restoreCounts := map[string]int64{}
	for _, table := range requiredPostgresTables {
		sourceCount, sourceErr := postgresTableCount(ctx, cfg, conn, conn.Database, table)
		restoreCount, restoreErr := postgresTableCount(ctx, cfg, conn, cfg.PostgresRestoreDB, table)
		passed := sourceErr == nil && restoreErr == nil && sourceCount == restoreCount
		detail := fmt.Sprintf("source=%d restore=%d", sourceCount, restoreCount)
		if sourceErr != nil {
			detail = sourceErr.Error()
		}
		if restoreErr != nil {
			detail = restoreErr.Error()
		}
		addCheck(checks, "postgres.table."+table+".row_count_match", passed, detail)
		if passed {
			summary.RestoredTables = append(summary.RestoredTables, table)
		}
		sourceCounts[table] = sourceCount
		restoreCounts[table] = restoreCount
	}
	sort.Strings(summary.RestoredTables)
	summary.SourceRowCounts = sourceCounts
	summary.RestoreRowCounts = restoreCounts
	cleanupPostgres(ctx, cfg, conn, containerDumpPath, checks, &summary)
	return summary
}

func cleanupPostgres(ctx context.Context, cfg Config, conn postgresConnection, containerDumpPath string, checks *[]Check, summary *PostgresSummary) {
	if !cfg.Cleanup {
		addCheck(checks, "postgres.restore_db.cleanup", true, "cleanup disabled; restore database kept")
		return
	}
	dropSQL := "DROP DATABASE IF EXISTS " + quoteIdent(cfg.PostgresRestoreDB) + " WITH (FORCE)"
	if _, _, err := runCommand(ctx, 30*time.Second, "docker", "exec", cfg.PostgresContainer, "psql", "-U", conn.User, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", dropSQL); err != nil {
		addCheck(checks, "postgres.restore_db.cleanup", false, err.Error())
		return
	}
	_, _, _ = runCommand(ctx, 10*time.Second, "docker", "exec", cfg.PostgresContainer, "rm", "-f", containerDumpPath)
	summary.CleanedUp = true
	addCheck(checks, "postgres.restore_db.cleanup", true, cfg.PostgresRestoreDB)
}

func postgresTableCount(ctx context.Context, cfg Config, conn postgresConnection, database string, table string) (int64, error) {
	query := "SELECT COUNT(*) FROM " + quoteIdent(table)
	stdout, _, err := runCommand(ctx, 20*time.Second, "docker", "exec", cfg.PostgresContainer, "psql", "-U", conn.User, "-d", database, "-At", "-v", "ON_ERROR_STOP=1", "-c", query)
	if err != nil {
		return 0, err
	}
	return strconv.ParseInt(strings.TrimSpace(stdout), 10, 64)
}

func dsnWithDatabase(dsn string, database string) (string, error) {
	if strings.Contains(dsn, "://") {
		parsed, err := url.Parse(dsn)
		if err != nil {
			return "", err
		}
		parsed.Path = "/" + database
		return parsed.String(), nil
	}
	fields := strings.Fields(dsn)
	found := false
	for i, field := range fields {
		if strings.HasPrefix(field, "dbname=") {
			fields[i] = "dbname=" + database
			found = true
			break
		}
	}
	if !found {
		fields = append(fields, "dbname="+database)
	}
	return strings.Join(fields, " "), nil
}

type postgresConnection struct {
	User     string
	Database string
}

func postgresConnectionFromDSN(dsn string) postgresConnection {
	conn := postgresConnection{User: "tryops", Database: "tryops"}
	if strings.Contains(dsn, "://") {
		parsed, err := url.Parse(dsn)
		if err == nil {
			if parsed.User != nil {
				if user := parsed.User.Username(); user != "" {
					conn.User = user
				}
			}
			if db := strings.Trim(parsed.Path, "/"); db != "" {
				conn.Database = db
			}
		}
		return conn
	}
	for _, field := range strings.Fields(dsn) {
		switch {
		case strings.HasPrefix(field, "user="):
			conn.User = strings.TrimPrefix(field, "user=")
		case strings.HasPrefix(field, "dbname="):
			conn.Database = strings.TrimPrefix(field, "dbname=")
		}
	}
	return conn
}

var identifierPattern = regexp.MustCompile(`[^a-zA-Z0-9_]+`)

func sanitizeIdentifier(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return "tryops_restore_drill"
	}
	value = identifierPattern.ReplaceAllString(value, "_")
	if value[0] >= '0' && value[0] <= '9' {
		value = "tryops_" + value
	}
	if len(value) > 50 {
		value = value[:50]
	}
	return value
}

func quoteIdent(value string) string {
	return `"` + strings.ReplaceAll(value, `"`, `""`) + `"`
}
