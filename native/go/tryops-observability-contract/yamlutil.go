package main

import (
	"encoding/json"
	"os"
	"sort"

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
	if value == nil {
		return map[string]interface{}{}
	}
	switch typed := value.(type) {
	case map[string]interface{}:
		return typed
	case map[interface{}]interface{}:
		converted := map[string]interface{}{}
		for key, item := range typed {
			converted[formatAny(key)] = item
		}
		return converted
	default:
		return map[string]interface{}{}
	}
}

func nestedObject(root map[string]interface{}, keys ...string) map[string]interface{} {
	current := root
	for _, key := range keys {
		current = object(current[key])
	}
	return current
}

func stringField(root map[string]interface{}, key string) string {
	value, ok := root[key]
	if !ok || value == nil {
		return ""
	}
	return formatAny(value)
}

func stringList(value interface{}) []string {
	values := []string{}
	switch typed := value.(type) {
	case []string:
		values = append(values, typed...)
	case []interface{}:
		for _, item := range typed {
			values = append(values, formatAny(item))
		}
	}
	return values
}

func mapKeys(values map[string]interface{}) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func hasString(values []string, expected string) bool {
	for _, value := range values {
		if value == expected {
			return true
		}
	}
	return false
}

func containsText(values []string, expected string) bool {
	for _, value := range values {
		if contains(value, expected) {
			return true
		}
	}
	return false
}

func formatAny(value interface{}) string {
	switch typed := value.(type) {
	case string:
		return typed
	case json.Number:
		return typed.String()
	default:
		payload, err := json.Marshal(typed)
		if err != nil {
			return ""
		}
		return string(payload)
	}
}
