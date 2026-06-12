package main

import "strings"

func stringValue(value interface{}) string {
	text, _ := value.(string)
	return strings.TrimSpace(text)
}

func lowerString(value interface{}) string {
	return strings.ToLower(stringValue(value))
}

func intValue(value interface{}) int {
	switch typed := value.(type) {
	case float64:
		return int(typed)
	case int:
		return typed
	default:
		return 0
	}
}

func boolValue(value interface{}) (bool, bool) {
	typed, ok := value.(bool)
	return typed, ok
}
