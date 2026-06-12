package main

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

var (
	traceIDPattern    = regexp.MustCompile(`^[0-9a-f]{32}$`)
	spanIDPattern     = regexp.MustCompile(`^[0-9a-f]{16}$`)
	traceFlagsPattern = regexp.MustCompile(`^[0-9a-f]{2}$`)
	sensitiveKeys     = map[string]bool{
		"prompt": true, "raw_prompt": true, "person_image_path": true,
		"garment_image_path": true, "output_image_path": true,
		"authorization": true, "api_key": true, "secret": true, "token": true,
	}
)

func validateEnvelope(envelope Envelope) Validation {
	errors := make([]string, 0)
	if envelope.SchemaVersion != EnvelopeSchema {
		errors = append(errors, "schema_version mismatch")
	}
	if !traceIDPattern.MatchString(envelope.TraceID) || allZero(envelope.TraceID) {
		errors = append(errors, "invalid trace_id")
	}
	if !spanIDPattern.MatchString(envelope.SpanID) || allZero(envelope.SpanID) {
		errors = append(errors, "invalid span_id")
	}
	if !traceFlagsPattern.MatchString(envelope.TraceFlags) {
		errors = append(errors, "invalid trace_flags")
	}
	expectedTraceparent := fmt.Sprintf("00-%s-%s-%s", envelope.TraceID, envelope.SpanID, envelope.TraceFlags)
	if envelope.Traceparent != expectedTraceparent {
		errors = append(errors, "traceparent does not match trace fields")
	}
	if strings.TrimSpace(envelope.Resource["service.name"]) == "" {
		errors = append(errors, "resource.service.name is required")
	}
	if strings.TrimSpace(envelope.Resource["service.version"]) == "" {
		errors = append(errors, "resource.service.version is required")
	}
	if strings.TrimSpace(envelope.EventName) == "" {
		errors = append(errors, "event_name is required")
	}
	if envelope.SeverityNumber <= 0 {
		errors = append(errors, "severity_number must be positive")
	}
	if hasSensitiveAttribute(envelope.Attributes) {
		errors = append(errors, "attributes contain sensitive raw fields")
	}
	return Validation{
		Language:  envelope.Language,
		Runtime:   envelope.Runtime,
		RequestID: envelope.RequestID,
		Passed:    len(errors) == 0,
		Errors:    errors,
	}
}

func allZero(value string) bool {
	for _, char := range value {
		if char != '0' {
			return false
		}
	}
	return true
}

func hasSensitiveAttribute(value interface{}) bool {
	switch typed := value.(type) {
	case map[string]interface{}:
		for key, item := range typed {
			if sensitiveKeys[strings.ToLower(key)] {
				return true
			}
			if hasSensitiveAttribute(item) {
				return true
			}
		}
	case []interface{}:
		for _, item := range typed {
			if hasSensitiveAttribute(item) {
				return true
			}
		}
	case string:
		lower := strings.ToLower(typed)
		return strings.Contains(lower, "bearer ") || strings.Contains(lower, "secret prompt")
	default:
		encoded, err := json.Marshal(typed)
		if err == nil {
			lower := strings.ToLower(string(encoded))
			return strings.Contains(lower, "bearer ") || strings.Contains(lower, "secret prompt")
		}
	}
	return false
}
