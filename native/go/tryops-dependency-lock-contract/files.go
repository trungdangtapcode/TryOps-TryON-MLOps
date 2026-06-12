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

func readText(root string, path string) (string, error) {
	body, err := os.ReadFile(joinRoot(root, path))
	if err != nil {
		return "", err
	}
	return string(body), nil
}

func readJSON[T any](root string, path string) (T, error) {
	var value T
	body, err := os.ReadFile(joinRoot(root, path))
	if err != nil {
		return value, err
	}
	return value, json.Unmarshal(body, &value)
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

func fileExists(root string, path string) bool {
	info, err := os.Stat(joinRoot(root, path))
	return err == nil && !info.IsDir()
}

func relPath(root string, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return filepath.ToSlash(path)
	}
	return filepath.ToSlash(rel)
}

func quotedValue(line string) string {
	first := strings.Index(line, "\"")
	last := strings.LastIndex(line, "\"")
	if first < 0 || last <= first {
		return ""
	}
	return line[first+1 : last]
}
