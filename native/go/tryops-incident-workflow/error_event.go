package main

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"strings"
)

func buildErrorEvent(generatedAt string, alert AlertSummary) ErrorEvent {
	fingerprint := fingerprintFor(alert.Workload + ":" + strings.Join(alert.AlertNames, ",") + ":bad-candidate-drill")
	return ErrorEvent{
		SchemaVersion:  errorEventSchema,
		Timestamp:      generatedAt,
		EventName:      "exception",
		SeverityText:   "ERROR",
		TraceID:        "7b3f1cfcb7bc46eab3f1cfcb7bc46eab",
		SpanID:         "4f92c4c1bcf0a781",
		ServiceName:    "tryops-api",
		ServiceVersion: "local-dev",
		Fingerprint:    fingerprint,
		Exception: Exception{
			Type:    "tryops.incident.BadCandidateRollback",
			Message: "bad VTON candidate crossed error-budget burn threshold and triggered rollback workflow",
		},
		Attributes: map[string]string{
			"tryops.alert.severity":        alert.Severity,
			"tryops.alert.workload":        alert.Workload,
			"tryops.incident.id":           "inc-bad-candidate-drill",
			"tryops.rollback.required":     "true",
			"tryops.error_tracking.origin": "native-go-contract",
		},
	}
}

func validateErrorEvent(event ErrorEvent) []string {
	var failures []string
	if event.SchemaVersion != errorEventSchema {
		failures = append(failures, "error event schema_version must be "+errorEventSchema)
	}
	if event.EventName == "" {
		failures = append(failures, "event_name is required")
	}
	if event.SeverityText == "" {
		failures = append(failures, "severity_text is required")
	}
	if event.ServiceName == "" {
		failures = append(failures, "service_name is required")
	}
	if !isHexID(event.TraceID, 32) {
		failures = append(failures, "trace_id must be a nonzero 32-character hex id")
	}
	if !isHexID(event.SpanID, 16) {
		failures = append(failures, "span_id must be a nonzero 16-character hex id")
	}
	if event.Fingerprint == "" {
		failures = append(failures, "fingerprint is required")
	}
	if event.Exception.Type == "" || event.Exception.Message == "" {
		failures = append(failures, "exception type and message are required")
	}
	return failures
}

func summarizeErrorTracking(event ErrorEvent) ErrorTrackingSummary {
	tracker := externalTracker()
	return ErrorTrackingSummary{
		LocalSchemaVersion: event.SchemaVersion,
		EventCount:         1,
		Fingerprint:        event.Fingerprint,
		TraceID:            event.TraceID,
		SpanID:             event.SpanID,
		ServiceName:        event.ServiceName,
		SeverityText:       event.SeverityText,
		ExternalTracker:    tracker,
	}
}

func externalTracker() ExternalTrackerSummary {
	for _, candidate := range []struct {
		env      string
		provider string
	}{
		{env: "GLITCHTIP_DSN", provider: "glitchtip"},
		{env: "TRYOPS_ERROR_TRACKING_DSN", provider: "sentry-compatible"},
		{env: "SENTRY_DSN", provider: "sentry-compatible"},
	} {
		if strings.TrimSpace(os.Getenv(candidate.env)) != "" {
			return ExternalTrackerSummary{
				Configured: true,
				Provider:   candidate.provider,
				Mode:       "dsn_configured",
				Detail:     candidate.env + " is present; external error tracker can receive the same fingerprinted event",
			}
		}
	}
	return ExternalTrackerSummary{
		Configured: false,
		Provider:   "glitchtip_or_sentry_compatible",
		Mode:       "local_contract_only",
		Detail:     "no GLITCHTIP_DSN, TRYOPS_ERROR_TRACKING_DSN, or SENTRY_DSN is configured in this workspace",
	}
}

func fingerprintFor(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])[:16]
}

func isHexID(value string, expected int) bool {
	if len(value) != expected {
		return false
	}
	if strings.Trim(value, "0") == "" {
		return false
	}
	for _, char := range value {
		if !strings.ContainsRune("0123456789abcdef", char) {
			return false
		}
	}
	return true
}
