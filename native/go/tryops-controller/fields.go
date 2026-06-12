package main

import "strconv"

func nestedMap(data map[string]interface{}, key string) map[string]interface{} {
	value, ok := data[key]
	if !ok {
		return map[string]interface{}{}
	}
	nested, ok := value.(map[string]interface{})
	if !ok {
		return map[string]interface{}{}
	}
	return nested
}

func stringField(data map[string]interface{}, key string) string {
	value, ok := data[key]
	if !ok || value == nil {
		return ""
	}
	switch typed := value.(type) {
	case string:
		return typed
	case float64:
		return strconv.FormatFloat(typed, 'f', -1, 64)
	case bool:
		if typed {
			return "true"
		}
		return "false"
	default:
		return ""
	}
}

func intField(data map[string]interface{}, key string) int {
	value, ok := data[key]
	if !ok || value == nil {
		return 0
	}
	switch typed := value.(type) {
	case int:
		return typed
	case float64:
		return int(typed)
	case string:
		parsed, err := strconv.Atoi(typed)
		if err != nil {
			return 0
		}
		return parsed
	default:
		return 0
	}
}

func labelPresent(pr map[string]interface{}, name string) bool {
	labels, ok := pr["labels"].([]interface{})
	if !ok {
		return false
	}
	for _, label := range labels {
		labelMap, ok := label.(map[string]interface{})
		if !ok {
			continue
		}
		if stringField(labelMap, "name") == name {
			return true
		}
	}
	return false
}

func boolField(data map[string]interface{}, key string) bool {
	value, ok := data[key]
	if !ok || value == nil {
		return false
	}
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		return typed == "true"
	default:
		return false
	}
}
