package main

import (
	"fmt"
	"os"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

func readYAML(path string) (map[string]interface{}, error) {
	body, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var data map[string]interface{}
	if err := yaml.Unmarshal(body, &data); err != nil {
		return nil, err
	}
	return data, nil
}

func object(value interface{}) map[string]interface{} {
	if typed, ok := value.(map[string]interface{}); ok {
		return typed
	}
	return map[string]interface{}{}
}

func objects(value interface{}) []map[string]interface{} {
	items, ok := value.([]interface{})
	if !ok {
		return nil
	}
	out := make([]map[string]interface{}, 0, len(items))
	for _, item := range items {
		out = append(out, object(item))
	}
	return out
}

func stringsFrom(value interface{}) []string {
	switch typed := value.(type) {
	case []interface{}:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			out = append(out, fmt.Sprint(item))
		}
		return out
	case []string:
		return append([]string{}, typed...)
	default:
		return nil
	}
}

func stringField(data map[string]interface{}, key string) string {
	if value, ok := data[key]; ok && value != nil {
		return fmt.Sprint(value)
	}
	return ""
}

func mapKeys(data map[string]bool) []string {
	keys := make([]string, 0, len(data))
	for key := range data {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func containsValue(values []string, expected string) bool {
	for _, value := range values {
		if value == expected {
			return true
		}
	}
	return false
}

func containsText(values []string, expected string) bool {
	for _, value := range values {
		if strings.Contains(value, expected) {
			return true
		}
	}
	return false
}

func addCheck(checks *[]Check, name string, passed bool, detail string) {
	if detail == "" {
		detail = "missing"
	}
	*checks = append(*checks, Check{Name: name, Passed: passed, Detail: detail})
}
