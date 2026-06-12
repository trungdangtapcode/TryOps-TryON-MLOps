package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

func joinRoot(root string, path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, filepath.Clean(path))
}

func relPath(root string, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil || strings.HasPrefix(rel, "..") {
		return filepath.ToSlash(path)
	}
	return filepath.ToSlash(rel)
}

func readText(root string, path string) (string, error) {
	payload, err := os.ReadFile(joinRoot(root, path))
	if err != nil {
		return "", err
	}
	return string(payload), nil
}

func readJSON(root string, path string, out any) error {
	payload, err := os.ReadFile(joinRoot(root, path))
	if err != nil {
		return err
	}
	return json.Unmarshal(payload, out)
}

func writeJSON(path string, payload any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	body, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(body, '\n'), 0o644)
}

func writeText(path string, payload string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(payload), 0o644)
}

func fileExists(root string, path string) bool {
	info, err := os.Stat(joinRoot(root, path))
	return err == nil && !info.IsDir()
}
