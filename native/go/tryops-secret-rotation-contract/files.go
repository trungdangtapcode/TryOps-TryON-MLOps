package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
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

func readYAML[T any](root string, path string) (T, error) {
	var value T
	body, err := os.ReadFile(joinRoot(root, path))
	if err != nil {
		return value, err
	}
	return value, yaml.Unmarshal(body, &value)
}

func readYAMLDocuments(root string, path string) ([]KubernetesDoc, error) {
	body, err := os.ReadFile(joinRoot(root, path))
	if err != nil {
		return nil, err
	}
	parts := strings.Split(string(body), "\n---")
	docs := make([]KubernetesDoc, 0, len(parts))
	for _, part := range parts {
		if strings.TrimSpace(part) == "" {
			continue
		}
		var doc KubernetesDoc
		if err := yaml.Unmarshal([]byte(part), &doc); err != nil {
			return nil, err
		}
		if doc.Kind != "" {
			docs = append(docs, doc)
		}
	}
	return docs, nil
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
