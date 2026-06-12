package main

import (
	"encoding/json"
	"os"
	"path/filepath"
)

func readJSON(path string) (map[string]interface{}, error) {
	payload, err := os.ReadFile(path)
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
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}

func objectField(data map[string]interface{}, key string) map[string]interface{} {
	value, _ := data[key].(map[string]interface{})
	return value
}

func arrayField(data map[string]interface{}, key string) []interface{} {
	value, _ := data[key].([]interface{})
	return value
}

func stringField(data map[string]interface{}, key string) string {
	value, _ := data[key].(string)
	return value
}

func boolFieldDefault(data map[string]interface{}, key string, defaultValue bool) bool {
	value, ok := data[key].(bool)
	if !ok {
		return defaultValue
	}
	return value
}

func numberField(data map[string]interface{}, key string) float64 {
	switch value := data[key].(type) {
	case float64:
		return value
	case int:
		return float64(value)
	case int64:
		return float64(value)
	default:
		return 0
	}
}
