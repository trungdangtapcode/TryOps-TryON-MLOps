package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
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

func stringField(data map[string]interface{}, key string) string {
	value, _ := data[key].(string)
	return value
}

func boolField(data map[string]interface{}, key string) (bool, bool) {
	value, ok := data[key].(bool)
	return value, ok
}

func boolFieldDefault(data map[string]interface{}, key string) bool {
	value, _ := boolField(data, key)
	return value
}

func numberField(data map[string]interface{}, key string) (float64, bool) {
	switch value := data[key].(type) {
	case float64:
		return value, true
	case int:
		return float64(value), true
	default:
		return 0, false
	}
}

func objectField(data map[string]interface{}, key string) map[string]interface{} {
	value, _ := data[key].(map[string]interface{})
	return value
}

func arrayField(data map[string]interface{}, key string) []interface{} {
	value, _ := data[key].([]interface{})
	return value
}

func formatValue(value interface{}) string {
	switch typed := value.(type) {
	case nil:
		return ""
	case string:
		return typed
	case bool:
		if typed {
			return "true"
		}
		return "false"
	case float64:
		return strconv.FormatFloat(typed, 'f', -1, 64)
	case int:
		return strconv.Itoa(typed)
	default:
		return fmt.Sprintf("%v", typed)
	}
}

func formatScalar(value interface{}) (string, bool) {
	switch value.(type) {
	case nil, string, bool, float64, int:
		formatted := formatValue(value)
		return formatted, formatted != ""
	default:
		return "", false
	}
}
