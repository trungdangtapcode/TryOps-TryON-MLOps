package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

var migrationFilePattern = regexp.MustCompile(`^([0-9]{3,})_([a-z0-9_]+)\.sql$`)

func loadMigrations(dir string) ([]Migration, []Check) {
	checks := []Check{}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, []Check{{Name: "migrations.dir.read", Passed: false, Detail: err.Error()}}
	}
	checks = append(checks, Check{Name: "migrations.dir.read", Passed: true, Detail: dir})

	files := []string{}
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".sql") {
			continue
		}
		files = append(files, entry.Name())
	}
	sort.Strings(files)

	migrations := make([]Migration, 0, len(files))
	seenVersions := map[string]bool{}
	for _, file := range files {
		matches := migrationFilePattern.FindStringSubmatch(file)
		validName := len(matches) == 3
		checks = append(checks, Check{
			Name:   fmt.Sprintf("migration.%s.name", file),
			Passed: validName,
			Detail: detail(validName, "versioned SQL filename", "expected NNN_name.sql"),
		})
		if !validName {
			continue
		}
		version := matches[1]
		name := matches[2]
		duplicate := seenVersions[version]
		checks = append(checks, Check{
			Name:   fmt.Sprintf("migration.%s.unique_version", version),
			Passed: !duplicate,
			Detail: detail(!duplicate, "version unique", "duplicate migration version"),
		})
		seenVersions[version] = true

		path := filepath.Join(dir, file)
		body, err := os.ReadFile(path)
		if err != nil {
			checks = append(checks, Check{Name: fmt.Sprintf("migration.%s.read", file), Passed: false, Detail: err.Error()})
			continue
		}
		sql := strings.TrimSpace(string(body))
		checks = append(checks, migrationSafetyChecks(file, sql)...)
		migrations = append(migrations, Migration{
			Version:  version,
			Name:     name,
			Path:     filepath.ToSlash(path),
			Checksum: checksum(sql),
			SQL:      sql,
		})
	}
	checks = append(checks, Check{
		Name:   "migrations.minimum_count",
		Passed: len(migrations) >= 2,
		Detail: fmt.Sprintf("%d migrations", len(migrations)),
	})
	checks = append(checks, requiredTableChecks(migrations)...)
	return migrations, checks
}

func migrationSafetyChecks(file string, sql string) []Check {
	lower := strings.ToLower(sql)
	return []Check{
		{
			Name:   fmt.Sprintf("migration.%s.has_create_table", file),
			Passed: strings.Contains(lower, "create table if not exists"),
			Detail: detail(strings.Contains(lower, "create table if not exists"), "idempotent table creation", "missing CREATE TABLE IF NOT EXISTS"),
		},
		{
			Name:   fmt.Sprintf("migration.%s.no_drop_table", file),
			Passed: !strings.Contains(lower, "drop table"),
			Detail: detail(!strings.Contains(lower, "drop table"), "destructive DROP TABLE absent", "DROP TABLE is not allowed"),
		},
		{
			Name:   fmt.Sprintf("migration.%s.no_truncate", file),
			Passed: !strings.Contains(lower, "truncate "),
			Detail: detail(!strings.Contains(lower, "truncate "), "TRUNCATE absent", "TRUNCATE is not allowed"),
		},
	}
}

func requiredTableChecks(migrations []Migration) []Check {
	combined := strings.ToLower(joinMigrationSQL(migrations))
	required := []string{"requests", "feedback", "jobs", "models", "audit_log", "tryops_quota_usage"}
	checks := make([]Check, 0, len(required))
	for _, table := range required {
		needle := "create table if not exists " + table
		found := strings.Contains(combined, needle)
		checks = append(checks, Check{
			Name:   fmt.Sprintf("schema.table.%s", table),
			Passed: found,
			Detail: detail(found, "required table migration present", "required table migration missing"),
		})
	}
	return checks
}

func joinMigrationSQL(migrations []Migration) string {
	parts := make([]string, 0, len(migrations))
	for _, migration := range migrations {
		parts = append(parts, migration.SQL)
	}
	return strings.Join(parts, "\n")
}

func checksum(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func detail(passed bool, good string, bad string) string {
	if passed {
		return good
	}
	return bad
}
