package main

import "time"

func sampleEnvelopes() []Envelope {
	now := time.Now().UTC().Format(time.RFC3339)
	return []Envelope{
		{
			SchemaVersion:     EnvelopeSchema,
			Timestamp:         now,
			ObservedTimestamp: now,
			Language:          "go",
			Runtime:           "go1.22",
			Component:         "native-validator",
			EventName:         "tryops.go.trace_envelope.validation",
			SeverityText:      "INFO",
			SeverityNumber:    9,
			TraceID:           "44444444444444444444444444444444",
			SpanID:            "5555555555555555",
			TraceFlags:        "01",
			Traceparent:       "00-44444444444444444444444444444444-5555555555555555-01",
			RequestID:         "req-go",
			Workload:          "platform",
			Resource: map[string]string{
				"service.name":           "tryops-native-go",
				"service.version":        "0.1.0",
				"telemetry.sdk.language": "go",
			},
			Attributes: map[string]interface{}{
				"endpoint": "native://trace-envelope",
				"status":   "validated",
			},
		},
	}
}
