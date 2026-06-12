package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func readText(root, path string) (string, error) {
	payload, err := os.ReadFile(rootJoin(root, path))
	if err != nil {
		return "", err
	}
	return string(payload), nil
}

func readJSON(root, path string) (map[string]interface{}, error) {
	payload, err := os.ReadFile(rootJoin(root, path))
	if err != nil {
		return nil, err
	}
	var data map[string]interface{}
	if err := json.Unmarshal(payload, &data); err != nil {
		return nil, err
	}
	return data, nil
}

func writeJSON(path string, report Report) error {
	if path == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}

func containsAll(text string, patterns []string) (bool, string) {
	var missing []string
	for _, pattern := range patterns {
		if !strings.Contains(text, pattern) {
			missing = append(missing, pattern)
		}
	}
	if len(missing) > 0 {
		return false, fmt.Sprintf("missing: %s", strings.Join(missing, ", "))
	}
	return true, fmt.Sprintf("found %d required tokens", len(patterns))
}

func stringField(data map[string]interface{}, key string) string {
	if value, ok := data[key].(string); ok {
		return value
	}
	return ""
}

func boolField(data map[string]interface{}, key string) (bool, bool) {
	if value, ok := data[key].(bool); ok {
		return value, true
	}
	return false, false
}

func arrayField(data map[string]interface{}, key string) []interface{} {
	if value, ok := data[key].([]interface{}); ok {
		return value
	}
	return nil
}
