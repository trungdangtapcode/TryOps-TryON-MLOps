package main

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const migrationTableSQL = `
CREATE TABLE IF NOT EXISTS tryops_schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);`

func configurePool(ctx context.Context, cfg Config) (*pgxpool.Pool, PoolSummary, []Check, error) {
	poolSummary := PoolSummary{
		Driver:     "pgxpool",
		MinConns:   cfg.MinConns,
		MaxConns:   cfg.MaxConns,
		Configured: cfg.MaxConns >= cfg.MinConns && cfg.MaxConns > 0,
	}
	checks := []Check{
		{Name: "pool.driver.pgxpool", Passed: true, Detail: "github.com/jackc/pgx/v5/pgxpool"},
		{Name: "pool.max_conns.valid", Passed: cfg.MaxConns >= cfg.MinConns && cfg.MaxConns > 0, Detail: fmt.Sprintf("min=%d max=%d", cfg.MinConns, cfg.MaxConns)},
	}
	if cfg.Mode != "apply" {
		return nil, poolSummary, checks, nil
	}
	if cfg.DSN == "" {
		checks = append(checks, Check{Name: "pool.dsn.present", Passed: false, Detail: "apply mode requires --dsn or TRYOPS_POSTGRES_MIGRATION_DSN"})
		return nil, poolSummary, checks, fmt.Errorf("apply mode requires a Postgres DSN")
	}
	checks = append(checks, Check{Name: "pool.dsn.present", Passed: true, Detail: "DSN configured"})

	poolConfig, err := pgxpool.ParseConfig(cfg.DSN)
	if err != nil {
		checks = append(checks, Check{Name: "pool.config.parse", Passed: false, Detail: err.Error()})
		return nil, poolSummary, checks, err
	}
	poolConfig.MinConns = cfg.MinConns
	poolConfig.MaxConns = cfg.MaxConns
	poolConfig.HealthCheckPeriod = 10 * time.Second
	pool, err := pgxpool.NewWithConfig(ctx, poolConfig)
	if err != nil {
		checks = append(checks, Check{Name: "pool.create", Passed: false, Detail: err.Error()})
		return nil, poolSummary, checks, err
	}
	if err := pool.Ping(ctx); err != nil {
		checks = append(checks, Check{Name: "pool.ping", Passed: false, Detail: err.Error()})
		pool.Close()
		return nil, poolSummary, checks, err
	}
	poolSummary.LivePing = true
	checks = append(checks, Check{Name: "pool.ping", Passed: true, Detail: "Postgres ping succeeded"})

	conn, err := pool.Acquire(ctx)
	if err != nil {
		checks = append(checks, Check{Name: "pool.acquire", Passed: false, Detail: err.Error()})
		pool.Close()
		return nil, poolSummary, checks, err
	}
	conn.Release()
	poolSummary.ConnectionAcquire = true
	checks = append(checks, Check{Name: "pool.acquire", Passed: true, Detail: "pooled connection acquired and released"})
	return pool, poolSummary, checks, nil
}

func applyMigrations(ctx context.Context, pool *pgxpool.Pool, migrations []Migration) ([]MigrationSummary, []Check, error) {
	summaries := migrationSummaries(migrations)
	checks := []Check{}
	if pool == nil {
		return summaries, checks, nil
	}

	if _, err := pool.Exec(ctx, migrationTableSQL); err != nil {
		checks = append(checks, Check{Name: "schema_migrations.create", Passed: false, Detail: err.Error()})
		return summaries, checks, err
	}
	checks = append(checks, Check{Name: "schema_migrations.create", Passed: true, Detail: "tryops_schema_migrations ready"})

	for index, migration := range migrations {
		applied, err := migrationApplied(ctx, pool, migration)
		if err != nil {
			checks = append(checks, Check{Name: fmt.Sprintf("migration.%s.query", migration.Version), Passed: false, Detail: err.Error()})
			return summaries, checks, err
		}
		if applied {
			summaries[index].Applied = true
			checks = append(checks, Check{Name: fmt.Sprintf("migration.%s.applied", migration.Version), Passed: true, Detail: "already applied"})
			continue
		}
		tx, err := pool.BeginTx(ctx, pgx.TxOptions{})
		if err != nil {
			checks = append(checks, Check{Name: fmt.Sprintf("migration.%s.begin", migration.Version), Passed: false, Detail: err.Error()})
			return summaries, checks, err
		}
		for statementIndex, statement := range splitStatements(migration.SQL) {
			if _, err := tx.Exec(ctx, statement); err != nil {
				_ = tx.Rollback(ctx)
				checks = append(checks, Check{Name: fmt.Sprintf("migration.%s.exec.%d", migration.Version, statementIndex+1), Passed: false, Detail: err.Error()})
				return summaries, checks, err
			}
		}
		if _, err := tx.Exec(ctx,
			"INSERT INTO tryops_schema_migrations (version, name, checksum_sha256) VALUES ($1, $2, $3)",
			migration.Version, migration.Name, migration.Checksum,
		); err != nil {
			_ = tx.Rollback(ctx)
			checks = append(checks, Check{Name: fmt.Sprintf("migration.%s.record", migration.Version), Passed: false, Detail: err.Error()})
			return summaries, checks, err
		}
		if err := tx.Commit(ctx); err != nil {
			checks = append(checks, Check{Name: fmt.Sprintf("migration.%s.commit", migration.Version), Passed: false, Detail: err.Error()})
			return summaries, checks, err
		}
		summaries[index].Applied = true
		checks = append(checks, Check{Name: fmt.Sprintf("migration.%s.applied", migration.Version), Passed: true, Detail: "migration applied"})
	}
	checks = append(checks, liveTableChecks(ctx, pool)...)
	return summaries, checks, nil
}

func splitStatements(sql string) []string {
	parts := strings.Split(sql, ";")
	statements := make([]string, 0, len(parts))
	for _, part := range parts {
		statement := strings.TrimSpace(part)
		if statement == "" {
			continue
		}
		statements = append(statements, statement)
	}
	return statements
}

func migrationApplied(ctx context.Context, pool *pgxpool.Pool, migration Migration) (bool, error) {
	var count int
	err := pool.QueryRow(ctx,
		"SELECT COUNT(*) FROM tryops_schema_migrations WHERE version=$1 AND checksum_sha256=$2",
		migration.Version, migration.Checksum,
	).Scan(&count)
	return count > 0, err
}

func liveTableChecks(ctx context.Context, pool *pgxpool.Pool) []Check {
	required := []string{"requests", "feedback", "jobs", "models", "audit_log", "tryops_quota_usage", "tryops_schema_migrations"}
	checks := make([]Check, 0, len(required))
	for _, table := range required {
		var exists bool
		err := pool.QueryRow(ctx, "SELECT to_regclass($1) IS NOT NULL", "public."+table).Scan(&exists)
		passed := err == nil && exists
		detail := "table exists"
		if err != nil {
			detail = err.Error()
		} else if !exists {
			detail = "table missing"
		}
		checks = append(checks, Check{Name: fmt.Sprintf("live.table.%s", table), Passed: passed, Detail: detail})
	}
	return checks
}

func migrationSummaries(migrations []Migration) []MigrationSummary {
	summaries := make([]MigrationSummary, 0, len(migrations))
	for _, migration := range migrations {
		summaries = append(summaries, MigrationSummary{
			Version:  migration.Version,
			Name:     migration.Name,
			Path:     migration.Path,
			Checksum: migration.Checksum,
		})
	}
	return summaries
}
