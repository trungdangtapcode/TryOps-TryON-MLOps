package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

func readJSON(root string, path string) (map[string]interface{}, error) {
	body, err := os.ReadFile(rootJoin(root, path))
	if err != nil {
		return nil, err
	}
	var data map[string]interface{}
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, err
	}
	return data, nil
}

func readText(root string, path string) string {
	body, err := os.ReadFile(rootJoin(root, path))
	if err != nil {
		return ""
	}
	return string(body)
}

func fileSize(root string, path string) int64 {
	info, err := os.Stat(rootJoin(root, path))
	if err != nil {
		return 0
	}
	return info.Size()
}

func writeReport(path string, report Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	body, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(body, '\n'), 0o644)
}

func firstVersionLine(output string) string {
	for _, line := range strings.Split(output, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		return line
	}
	return ""
}
