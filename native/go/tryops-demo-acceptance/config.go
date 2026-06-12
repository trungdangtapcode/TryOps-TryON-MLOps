package main

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type config struct {
	Root            string
	OutputPath      string
	Timeout         time.Duration
	RunGate         bool
	RefreshEvidence bool
	RefreshStack    bool
}

func parseConfig() config {
	cfg := config{}
	flag.StringVar(&cfg.Root, "root", getenv("TRYOPS_ROOT", "."), "repository root")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_DEMO_ACCEPTANCE_OUTPUT", "artifacts/eval/demo_acceptance/professor_demo_acceptance.json"), "JSON report output path")
	flag.DurationVar(&cfg.Timeout, "timeout", 25*time.Minute, "total command execution timeout")
	flag.BoolVar(&cfg.RunGate, "run-gate", true, "execute the live bad-candidate policy gate")
	flag.BoolVar(&cfg.RefreshEvidence, "refresh-evidence", false, "rerun heavier demo evidence commands before validation")
	flag.BoolVar(&cfg.RefreshStack, "refresh-stack", false, "run make app-smoke before validation")
	flag.Parse()

	cfg.Root = cleanRoot(cfg.Root)
	cfg.OutputPath = resolvePath(cfg.Root, cfg.OutputPath)
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
