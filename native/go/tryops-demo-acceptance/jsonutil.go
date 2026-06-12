package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func readJSONObject(path string) (map[string]interface{}, error) {
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

func boolField(data map[string]interface{}, key string) bool {
	value, _ := data[key].(bool)
	return value
}

func numberField(data map[string]interface{}, key string) float64 {
	value, _ := data[key].(float64)
	return value
}

func objectField(data map[string]interface{}, key string) map[string]interface{} {
	value, _ := data[key].(map[string]interface{})
	return value
}

func arrayField(data map[string]interface{}, key string) []interface{} {
	value, _ := data[key].([]interface{})
	return value
}

func nestedObject(data map[string]interface{}, keys ...string) map[string]interface{} {
	current := data
	for _, key := range keys {
		current = objectField(current, key)
		if current == nil {
			return nil
		}
	}
	return current
}

func nestedArray(data map[string]interface{}, keys ...string) []interface{} {
	if len(keys) == 0 {
		return nil
	}
	parent := nestedObject(data, keys[:len(keys)-1]...)
	if parent == nil {
		return nil
	}
	return arrayField(parent, keys[len(keys)-1])
}

func requireSchema(data map[string]interface{}, want string) []string {
	if got := stringField(data, "schema_version"); got != want {
		return []string{fmt.Sprintf("schema_version %q != %q", got, want)}
	}
	return nil
}
