package main

import (
	"flag"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

func parseConfig() Config {
	root := flag.String("root", getenv("TRYOPS_ROOT", "."), "repository root")
	migrationsDir := flag.String("migrations", getenv("TRYOPS_POSTGRES_MIGRATIONS_DIR", "infra/postgres/migrations"), "Postgres migration directory")
	output := flag.String("output", getenv("TRYOPS_POSTGRES_MIGRATION_OUTPUT", "artifacts/eval/postgres/native_postgres_migration.json"), "report output path")
	dsn := flag.String("dsn", firstEnv("TRYOPS_POSTGRES_MIGRATION_DSN", "TRYOPS_DATABASE_URL"), "Postgres DSN for apply mode")
	mode := flag.String("mode", getenv("TRYOPS_POSTGRES_MIGRATION_MODE", "plan"), "plan or apply")
	minConns := flag.Int("min-conns", envInt("TRYOPS_POSTGRES_POOL_MIN_CONNS", 1), "minimum pool connections")
	maxConns := flag.Int("max-conns", envInt("TRYOPS_POSTGRES_POOL_MAX_CONNS", 8), "maximum pool connections")
	flag.Parse()

	cfg := Config{
		Root:          filepath.Clean(*root),
		MigrationsDir: *migrationsDir,
		OutputPath:    *output,
		DSN:           strings.TrimSpace(*dsn),
		Mode:          strings.ToLower(strings.TrimSpace(*mode)),
		MinConns:      int32(*minConns),
		MaxConns:      int32(*maxConns),
	}
	if !filepath.IsAbs(cfg.MigrationsDir) {
		cfg.MigrationsDir = filepath.Join(cfg.Root, cfg.MigrationsDir)
	}
	if !filepath.IsAbs(cfg.OutputPath) {
		cfg.OutputPath = filepath.Join(cfg.Root, cfg.OutputPath)
	}
	return cfg
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

func envInt(name string, fallback int) int {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}
