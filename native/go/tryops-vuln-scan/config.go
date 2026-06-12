package main

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type config struct {
	Root           string
	OutputPath     string
	NPMAuditOutput string
	Timeout        time.Duration
}

func parseConfig() config {
	cfg := config{}
	flag.StringVar(&cfg.Root, "root", getenv("TRYOPS_ROOT", "."), "repository root")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_VULN_SCAN_OUTPUT", "artifacts/eval/security/vulnerability_scan_report.json"), "JSON report output path")
	flag.StringVar(&cfg.NPMAuditOutput, "npm-audit-output", getenv("TRYOPS_NPM_AUDIT_OUTPUT", "artifacts/eval/security/npm_audit_web.json"), "raw npm audit JSON output path")
	flag.DurationVar(&cfg.Timeout, "timeout", 2*time.Minute, "scan timeout")
	flag.Parse()
	cfg.Root = cleanRoot(cfg.Root)
	cfg.OutputPath = resolvePath(cfg.Root, cfg.OutputPath)
	cfg.NPMAuditOutput = resolvePath(cfg.Root, cfg.NPMAuditOutput)
	return cfg
}

func getenv(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func cleanRoot(root string) string {
	root = strings.TrimSpace(root)
	if root == "" {
		root = "."
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		return root
	}
	return abs
}

func resolvePath(root string, path string) string {
	path = strings.TrimSpace(path)
	if path == "" || filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}
