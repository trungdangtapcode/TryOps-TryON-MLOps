package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

var requiredLanguages = []string{"rust", "go", "cpp", "fastapi"}

func buildReport(envelopes []Envelope, source Source) Report {
	validations := make([]Validation, 0, len(envelopes))
	summary := Summary{
		TotalEnvelopes: len(envelopes),
		ByLanguage:     map[string]int{},
	}
	passed := true
	for _, envelope := range envelopes {
		validation := validateEnvelope(envelope)
		validations = append(validations, validation)
		summary.ByLanguage[envelope.Language]++
		if validation.Passed {
			summary.PassedEnvelopes++
		} else {
			summary.FailedEnvelopes++
			passed = false
		}
	}
	summary.RequiredCovered = coversRequiredLanguages(summary.ByLanguage)
	if !summary.RequiredCovered {
		passed = false
	}
	return Report{
		SchemaVersion: ReportSchema,
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		CoverageLevel: "native_contract",
		Contract:      EnvelopeSchema,
		Research: []ResearchSource{
			{
				Name: "W3C Trace Context",
				URL:  "https://www.w3.org/TR/trace-context/",
				Use:  "traceparent, trace-id, parent-id/span-id, and trace-flags constraints",
			},
			{
				Name: "OpenTelemetry Logs Data Model",
				URL:  "https://opentelemetry.io/docs/specs/otel/logs/data-model/",
				Use:  "log envelope fields for trace/span correlation, severity, resource, attributes, and event name",
			},
			{
				Name: "OpenTelemetry Resource Semantic Conventions",
				URL:  "https://opentelemetry.io/docs/specs/semconv/resource/",
				Use:  "service.name and service.version resource identity",
			},
		},
		Sources:     []Source{source},
		Summary:     summary,
		Validations: validations,
		Envelopes:   envelopes,
	}
}

func coversRequiredLanguages(counts map[string]int) bool {
	for _, language := range requiredLanguages {
		if counts[language] == 0 {
			return false
		}
	}
	return true
}

func writeJSON(path string, value interface{}) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	encoded, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(encoded, '\n'), 0o644)
}
