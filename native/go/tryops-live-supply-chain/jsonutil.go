package main

func stringField(data map[string]interface{}, key string) string {
	if value, ok := data[key].(string); ok {
		return value
	}
	return ""
}

func intField(data map[string]interface{}, key string) int {
	switch value := data[key].(type) {
	case float64:
		return int(value)
	case int:
		return value
	default:
		return 0
	}
}

func arrayField(data map[string]interface{}, key string) []interface{} {
	if value, ok := data[key].([]interface{}); ok {
		return value
	}
	return nil
}
