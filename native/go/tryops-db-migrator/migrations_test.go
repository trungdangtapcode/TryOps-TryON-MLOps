package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestLoadMigrationsValidatesRequiredTables(t *testing.T) {
	dir := t.TempDir()
	mustWrite(t, filepath.Join(dir, "001_product_schema.sql"), `
CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS audit_log (id TEXT PRIMARY KEY);
`)
	mustWrite(t, filepath.Join(dir, "002_quota_usage.sql"), `
CREATE TABLE IF NOT EXISTS tryops_quota_usage (period TEXT NOT NULL);
`)

	migrations, checks := loadMigrations(dir)

	if len(migrations) != 2 {
		t.Fatalf("migrations = %d, want 2", len(migrations))
	}
	if failed := failedChecks(checks); len(failed) != 0 {
		t.Fatalf("unexpected failed checks: %+v", failed)
	}
	if migrations[0].Checksum == "" {
		t.Fatalf("expected checksum")
	}
}

func TestLoadMigrationsFailsMissingRequiredTable(t *testing.T) {
	dir := t.TempDir()
	mustWrite(t, filepath.Join(dir, "001_product_schema.sql"), `
CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY);
`)
	mustWrite(t, filepath.Join(dir, "002_quota_usage.sql"), `
CREATE TABLE IF NOT EXISTS tryops_quota_usage (period TEXT NOT NULL);
`)

	_, checks := loadMigrations(dir)

	if !hasFailedCheck(checks, "schema.table.audit_log") {
		t.Fatalf("expected missing audit_log check, got %+v", checks)
	}
}

func TestPlanReportUsesPoolContractWithoutConnecting(t *testing.T) {
	dir := t.TempDir()
	mustWrite(t, filepath.Join(dir, "001_product_schema.sql"), `
CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS audit_log (id TEXT PRIMARY KEY);
`)
	mustWrite(t, filepath.Join(dir, "002_quota_usage.sql"), `
CREATE TABLE IF NOT EXISTS tryops_quota_usage (period TEXT NOT NULL);
`)

	report, err := buildReport(context.Background(), Config{
		MigrationsDir: dir,
		Mode:          "plan",
		MinConns:      1,
		MaxConns:      8,
	})

	if err != nil {
		t.Fatal(err)
	}
	if !report.Passed {
		t.Fatalf("expected report to pass: %+v", failedChecks(report.Checks))
	}
	if report.Pool.Driver != "pgxpool" || report.Summary.PoolMaxConns != 8 {
		t.Fatalf("unexpected pool summary: %+v", report.Pool)
	}
}

func mustWrite(t *testing.T, path string, body string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func failedChecks(checks []Check) []Check {
	failed := []Check{}
	for _, check := range checks {
		if !check.Passed {
			failed = append(failed, check)
		}
	}
	return failed
}

func hasFailedCheck(checks []Check, name string) bool {
	for _, check := range checks {
		if check.Name == name && !check.Passed {
			return true
		}
	}
	return false
}
