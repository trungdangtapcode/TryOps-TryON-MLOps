package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestDSNWithDatabaseURL(t *testing.T) {
	got, err := dsnWithDatabase("postgres://tryops:secret@127.0.0.1:15432/tryops?sslmode=disable", "tryops_restore_drill")
	if err != nil {
		t.Fatal(err)
	}
	want := "postgres://tryops:secret@127.0.0.1:15432/tryops_restore_drill?sslmode=disable"
	if got != want {
		t.Fatalf("dsnWithDatabase mismatch\nwant: %s\n got: %s", want, got)
	}
}

func TestDSNWithDatabaseKeywords(t *testing.T) {
	got, err := dsnWithDatabase("host=postgres port=5432 user=tryops dbname=tryops sslmode=disable", "postgres")
	if err != nil {
		t.Fatal(err)
	}
	want := "host=postgres port=5432 user=tryops dbname=postgres sslmode=disable"
	if got != want {
		t.Fatalf("keyword DSN mismatch\nwant: %s\n got: %s", want, got)
	}
}

func TestSanitizeAndQuoteIdentifier(t *testing.T) {
	if got := sanitizeIdentifier("123 bad-name!"); got != "tryops_123_bad_name_" {
		t.Fatalf("unexpected sanitized identifier: %s", got)
	}
	if got := quoteIdent(`tryops"restore`); got != `"tryops""restore"` {
		t.Fatalf("unexpected quoted identifier: %s", got)
	}
}

func TestEvaluatePlanReadsComposeAndSchedule(t *testing.T) {
	dir := t.TempDir()
	composePath := filepath.Join(dir, "docker-compose.yml")
	schedulePath := filepath.Join(dir, "restore_drill.cron")
	if err := os.WriteFile(composePath, []byte(`
services:
  postgres:
    image: postgres:16
    volumes:
      - postgres-data:/var/lib/postgresql/data
    secrets:
      - tryops_postgres_password
  minio:
    image: minio/minio:latest
    volumes:
      - minio-data:/data
    secrets:
      - tryops_minio_root_user
      - tryops_minio_root_password
volumes:
  postgres-data:
  minio-data:
secrets:
  tryops_postgres_password:
  tryops_minio_root_user:
  tryops_minio_root_password:
`), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(schedulePath, []byte("17 3 * * * cd /opt/tryops && make native-backup-restore-live >> /var/log/tryops/restore-drill.log 2>&1\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	cfg := Config{
		Root:               dir,
		Mode:               "plan",
		ComposePath:        composePath,
		SchedulePath:       schedulePath,
		BackupDir:          filepath.Join(dir, "backups"),
		PostgresContainer:  "flow-postgres-1",
		PostgresRestoreDB:  "tryops_restore_drill",
		MinIOContainer:     "flow-minio-1",
		MinIOBucket:        "tryops-artifacts",
		MinIORestoreBucket: "tryops-restore-drill",
	}
	report := evaluate(context.Background(), cfg)
	if !report.Passed {
		t.Fatalf("expected plan report to pass: %#v", report.Checks)
	}
	if report.CoverageLevel != "native_backup_restore_plan_contract" {
		t.Fatalf("unexpected coverage: %s", report.CoverageLevel)
	}
	if report.Summary.PlanChecks < 10 {
		t.Fatalf("expected plan checks, got %d", report.Summary.PlanChecks)
	}
}
