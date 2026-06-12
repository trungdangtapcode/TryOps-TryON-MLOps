package main

import "testing"

func TestValidateEnvelopeAcceptsGoSample(t *testing.T) {
	envelope := sampleEnvelopes()[0]
	validation := validateEnvelope(envelope)
	if !validation.Passed {
		t.Fatalf("expected sample to pass: %#v", validation.Errors)
	}
}

func TestValidateEnvelopeRejectsZeroTraceAndSensitivePrompt(t *testing.T) {
	envelope := sampleEnvelopes()[0]
	envelope.TraceID = "00000000000000000000000000000000"
	envelope.Traceparent = "00-00000000000000000000000000000000-5555555555555555-01"
	envelope.Attributes["prompt"] = "secret prompt must not be present"
	validation := validateEnvelope(envelope)
	if validation.Passed {
		t.Fatalf("expected invalid envelope to fail")
	}
	if !contains(validation.Errors, "invalid trace_id") {
		t.Fatalf("expected invalid trace error: %#v", validation.Errors)
	}
	if !contains(validation.Errors, "attributes contain sensitive raw fields") {
		t.Fatalf("expected sensitive attribute error: %#v", validation.Errors)
	}
}

func TestBuildReportRequiresAllLanguages(t *testing.T) {
	report := buildReport(sampleEnvelopes(), Source{Name: "test", Present: true})
	if report.Passed {
		t.Fatalf("single-language report should not pass required coverage")
	}
	if report.Summary.RequiredCovered {
		t.Fatalf("expected missing language coverage")
	}
}

func contains(values []string, expected string) bool {
	for _, value := range values {
		if value == expected {
			return true
		}
	}
	return false
}
