package main

import (
	"fmt"
	"sort"
	"strings"
)

func renderNativePolicyWire(candidate NativePolicyCandidate, targetStage string) string {
	var builder strings.Builder
	writePolicyLine(&builder, "target_stage", targetStage)
	writePolicyLine(&builder, "candidate_id", candidate.CandidateID)
	writePolicyLine(&builder, "workload", candidate.Workload)
	writePolicyLine(&builder, "model_name", candidate.ModelName)
	writePolicyLine(&builder, "model_version", candidate.ModelVersion)
	writePolicyLine(&builder, "risk_status", candidate.RiskStatus)
	writePolicyLine(&builder, "signed", boolString(candidate.Signed))
	writePolicyLine(&builder, "critical_vulnerabilities", fmt.Sprint(candidate.Vulnerabilities["critical"]))
	writePolicyLine(&builder, "high_vulnerabilities", fmt.Sprint(candidate.Vulnerabilities["high"]))

	for _, key := range sortedFloatKeys(candidate.Metrics) {
		writePolicyLine(&builder, "metric."+key, fmt.Sprint(candidate.Metrics[key]))
	}
	for _, key := range sortedStringKeys(candidate.Artifacts) {
		writePolicyLine(&builder, "artifact."+key, candidate.Artifacts[key])
	}
	metadata := flattenPolicyMetadata(candidate.Metadata)
	for _, key := range sortedStringKeys(metadata) {
		writePolicyLine(&builder, "metadata."+key, metadata[key])
	}
	for _, approval := range candidate.Approvals {
		writePolicyLine(&builder, "approval", approval)
	}
	return builder.String()
}

func writePolicyLine(builder *strings.Builder, key string, value string) {
	builder.WriteString(key)
	builder.WriteString("=")
	builder.WriteString(sanitizePolicyValue(value))
	builder.WriteString("\n")
}

func flattenPolicyMetadata(metadata map[string]interface{}) map[string]string {
	out := map[string]string{}
	for key, value := range metadata {
		flattenPolicyMetadataValue(out, key, value)
	}
	return out
}

func flattenPolicyMetadataValue(out map[string]string, key string, value interface{}) {
	switch typed := value.(type) {
	case map[string]interface{}:
		for nestedKey, nestedValue := range typed {
			flattenPolicyMetadataValue(out, key+"."+nestedKey, nestedValue)
		}
	case []interface{}:
		parts := make([]string, 0, len(typed))
		for _, item := range typed {
			if part := scalarToString(item); part != "" {
				parts = append(parts, part)
			}
		}
		out[key] = strings.Join(parts, ",")
	case []string:
		out[key] = strings.Join(typed, ",")
	case bool:
		out[key] = boolString(typed)
	default:
		out[key] = scalarToString(typed)
	}
}

func sanitizePolicyValue(value string) string {
	replacer := strings.NewReplacer("\n", " ", "\r", " ", "\x00", "")
	return replacer.Replace(value)
}

func boolString(value bool) string {
	if value {
		return "true"
	}
	return "false"
}

func sortedStringKeys(values map[string]string) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func sortedFloatKeys(values map[string]float64) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}
