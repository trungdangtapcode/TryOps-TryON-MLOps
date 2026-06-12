package main

import (
	"fmt"
	"strconv"
)

func nativePolicyCandidateFromValue(value interface{}) (NativePolicyCandidate, error) {
	data, ok := mapFromValue(value)
	if !ok {
		return NativePolicyCandidate{}, fmt.Errorf("policy_candidate must be an object")
	}
	candidate := NativePolicyCandidate{
		CandidateID:     stringField(data, "candidate_id"),
		Workload:        stringField(data, "workload"),
		ModelName:       firstNonEmpty(stringField(data, "model_name"), stringField(data, "name")),
		ModelVersion:    firstNonEmpty(stringField(data, "model_version"), stringField(data, "version")),
		Metrics:         floatMapField(data, "metrics"),
		Artifacts:       stringMapField(data, "artifacts"),
		Approvals:       stringSliceField(data, "approvals"),
		RiskStatus:      firstNonEmpty(stringField(data, "risk_status"), "unknown"),
		Vulnerabilities: intMapField(data, "vulnerabilities"),
		Signed:          boolField(data, "signed"),
		Metadata:        metadataField(data, "metadata"),
	}
	if candidate.CandidateID == "" {
		return NativePolicyCandidate{}, fmt.Errorf("policy_candidate.candidate_id is required")
	}
	if candidate.Workload == "" {
		return NativePolicyCandidate{}, fmt.Errorf("policy_candidate.workload is required")
	}
	if candidate.ModelName == "" {
		return NativePolicyCandidate{}, fmt.Errorf("policy_candidate.model_name is required")
	}
	if candidate.ModelVersion == "" {
		return NativePolicyCandidate{}, fmt.Errorf("policy_candidate.model_version is required")
	}
	if len(candidate.Metrics) == 0 {
		return NativePolicyCandidate{}, fmt.Errorf("policy_candidate.metrics is required")
	}
	if len(candidate.Artifacts) == 0 {
		return NativePolicyCandidate{}, fmt.Errorf("policy_candidate.artifacts is required")
	}
	return candidate, nil
}

func mapFromValue(value interface{}) (map[string]interface{}, bool) {
	if value == nil {
		return nil, false
	}
	switch typed := value.(type) {
	case map[string]interface{}:
		return typed, true
	default:
		return nil, false
	}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

func stringSliceField(data map[string]interface{}, key string) []string {
	value, ok := data[key]
	if !ok || value == nil {
		return []string{}
	}
	switch typed := value.(type) {
	case []interface{}:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			if asString := scalarToString(item); asString != "" {
				out = append(out, asString)
			}
		}
		return out
	case []string:
		return append([]string{}, typed...)
	case string:
		if typed == "" {
			return []string{}
		}
		return []string{typed}
	default:
		return []string{}
	}
}

func stringMapField(data map[string]interface{}, key string) map[string]string {
	value, ok := mapFromValue(data[key])
	if !ok {
		return map[string]string{}
	}
	out := make(map[string]string, len(value))
	for itemKey, itemValue := range value {
		out[itemKey] = scalarToString(itemValue)
	}
	return out
}

func floatMapField(data map[string]interface{}, key string) map[string]float64 {
	value, ok := mapFromValue(data[key])
	if !ok {
		return map[string]float64{}
	}
	out := make(map[string]float64, len(value))
	for itemKey, itemValue := range value {
		switch typed := itemValue.(type) {
		case float64:
			out[itemKey] = typed
		case int:
			out[itemKey] = float64(typed)
		case string:
			if parsed, err := strconv.ParseFloat(typed, 64); err == nil {
				out[itemKey] = parsed
			}
		}
	}
	return out
}

func intMapField(data map[string]interface{}, key string) map[string]int {
	value, ok := mapFromValue(data[key])
	if !ok {
		return map[string]int{}
	}
	out := make(map[string]int, len(value))
	for itemKey, itemValue := range value {
		switch typed := itemValue.(type) {
		case float64:
			out[itemKey] = int(typed)
		case int:
			out[itemKey] = typed
		case string:
			if parsed, err := strconv.Atoi(typed); err == nil {
				out[itemKey] = parsed
			}
		}
	}
	return out
}

func metadataField(data map[string]interface{}, key string) map[string]interface{} {
	value, ok := mapFromValue(data[key])
	if !ok {
		return map[string]interface{}{}
	}
	return value
}

func scalarToString(value interface{}) string {
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
		return fmt.Sprint(typed)
	}
}
