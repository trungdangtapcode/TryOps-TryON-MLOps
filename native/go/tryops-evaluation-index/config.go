package main

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
)

type config struct {
	Root       string
	OutputPath string
}

func parseConfig() config {
	cfg := config{}
	flag.StringVar(&cfg.Root, "root", getenv("TRYOPS_ROOT", "."), "repository root")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_EVALUATION_INDEX_OUTPUT", "artifacts/eval/evaluation_index/evaluation_index.json"), "JSON index output path")
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
