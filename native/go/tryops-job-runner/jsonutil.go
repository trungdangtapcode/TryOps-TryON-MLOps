package main

import "strings"

func stringField(data map[string]interface{}, key string) string {
	if data == nil {
		return ""
	}
	value, ok := data[key]
	if !ok || value == nil {
		return ""
	}
	text, ok := value.(string)
	if !ok {
		return ""
	}
	return strings.TrimSpace(text)
}

func lowerField(data map[string]interface{}, key string) string {
	return strings.ToLower(stringField(data, key))
}

func objectField(data map[string]interface{}, key string) map[string]interface{} {
	if data == nil {
		return nil
	}
	value, ok := data[key]
	if !ok || value == nil {
		return nil
	}
	object, ok := value.(map[string]interface{})
	if !ok {
		return nil
	}
	return object
}
