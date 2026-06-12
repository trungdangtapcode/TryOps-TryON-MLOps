package main

import (
	"context"
	"time"
)

func buildReport(ctx context.Context, cfg Config) (Report, error) {
	migrations, checks := loadMigrations(cfg.MigrationsDir)
	pool, poolSummary, poolChecks, poolErr := configurePool(ctx, cfg)
	checks = append(checks, poolChecks...)
	if pool != nil {
		defer pool.Close()
	}

	summaries := migrationSummaries(migrations)
	if poolErr == nil {
		applySummaries, applyChecks, err := applyMigrations(ctx, pool, migrations)
		checks = append(checks, applyChecks...)
		if len(applySummaries) > 0 {
			summaries = applySummaries
		}
		if err != nil {
			poolErr = err
		}
	}

	passedChecks := 0
	for _, check := range checks {
		if check.Passed {
			passedChecks++
		}
	}
	applied := 0
	for _, migration := range summaries {
		if migration.Applied {
			applied++
		}
	}
	passed := poolErr == nil && passedChecks == len(checks) && len(migrations) > 0
	report := Report{
		SchemaVersion: "tryops.native_postgres_migration.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		CoverageLevel: coverageLevel(cfg.Mode, poolSummary.LivePing),
		Mode:          cfg.Mode,
		Summary: Summary{
			TotalMigrations:   len(migrations),
			AppliedMigrations: applied,
			RequiredTables:    6,
			PassedChecks:      passedChecks,
			TotalChecks:       len(checks),
			PoolMaxConns:      cfg.MaxConns,
			LiveApply:         cfg.Mode == "apply" && poolSummary.LivePing,
		},
		Pool:       poolSummary,
		Migrations: summaries,
		Checks:     checks,
		Research: []ResearchSource{
			{
				Name: "PostgreSQL CREATE TABLE",
				URL:  "https://www.postgresql.org/docs/current/sql-createtable.html",
				Use:  "idempotent product schema migrations",
			},
			{
				Name: "pgxpool",
				URL:  "https://pkg.go.dev/github.com/jackc/pgx/v5/pgxpool",
				Use:  "native Go Postgres connection pooling",
			},
			{
				Name: "PostgreSQL application connection settings",
				URL:  "https://www.postgresql.org/docs/current/libpq-connect.html",
				Use:  "DSN-compatible production Postgres connection profile",
			},
		},
		Notes: []string{
			"Plan mode validates migration files, required tables, and pool configuration without connecting to Postgres.",
			"Apply mode uses pgxpool, records checksums in tryops_schema_migrations, and verifies live tables after migration.",
		},
	}
	return report, poolErr
}

func coverageLevel(mode string, live bool) string {
	if mode == "apply" && live {
		return "native_postgres_live_migration_pool_apply"
	}
	return "native_postgres_migration_pool_contract"
}
