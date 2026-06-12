package main

import "strings"

func modelIDs(data map[string]interface{}) []string {
	raw, _ := data["data"].([]interface{})
	ids := make([]string, 0, len(raw))
	for _, item := range raw {
		object, _ := item.(map[string]interface{})
		id, _ := object["id"].(string)
		id = strings.TrimSpace(id)
		if id != "" {
			ids = append(ids, id)
		}
	}
	return ids
}

func fillUsage(data map[string]interface{}, prompt *int, completion *int, total *int) {
	usage, _ := data["usage"].(map[string]interface{})
	*prompt = intField(usage, "prompt_tokens")
	*completion = intField(usage, "completion_tokens")
	*total = intField(usage, "total_tokens")
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

func firstAssistantText(data map[string]interface{}) string {
	choices, _ := data["choices"].([]interface{})
	if len(choices) == 0 {
		return ""
	}
	choice, _ := choices[0].(map[string]interface{})
	message, _ := choice["message"].(map[string]interface{})
	content, _ := message["content"].(string)
	if content != "" {
		return content
	}
	text, _ := choice["text"].(string)
	return text
}

func previewText(value string, limit int) string {
	value = strings.TrimSpace(value)
	if len(value) <= limit {
		return value
	}
	return value[:limit] + "..."
}

func sampleMetricNames(body string, limit int) []string {
	names := []string{}
	seen := map[string]bool{}
	for _, line := range strings.Split(body, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) == 0 {
			continue
		}
		name := fields[0]
		if brace := strings.Index(name, "{"); brace >= 0 {
			name = name[:brace]
		}
		if !strings.Contains(name, "vllm") || seen[name] {
			continue
		}
		seen[name] = true
		names = append(names, name)
		if len(names) >= limit {
			return names
		}
	}
	return names
}
