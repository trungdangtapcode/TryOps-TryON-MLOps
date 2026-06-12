package main

import (
	"fmt"
	"strings"
	"time"
)

var supportedEventTypes = map[string]bool{
	"tryops.promotion.decision": true,
	"tryops.feedback.created":   true,
	"tryops.incident.updated":   true,
	"tryops.quota.decision":     true,
}

func validateEvents(events []Event) error {
	if len(events) == 0 {
		return fmt.Errorf("no events to dispatch")
	}
	seen := map[string]bool{}
	for i := range events {
		if err := normalizeEvent(&events[i]); err != nil {
			return fmt.Errorf("event[%d]: %w", i, err)
		}
		if seen[events[i].ID] {
			return fmt.Errorf("event[%d]: duplicate id %q", i, events[i].ID)
		}
		seen[events[i].ID] = true
	}
	return nil
}

func normalizeEvent(event *Event) error {
	event.SpecVersion = strings.TrimSpace(event.SpecVersion)
	event.ID = strings.TrimSpace(event.ID)
	event.Source = strings.TrimSpace(event.Source)
	event.Type = strings.TrimSpace(event.Type)
	event.Subject = strings.TrimSpace(event.Subject)
	event.Time = strings.TrimSpace(event.Time)
	event.DataContentType = strings.TrimSpace(event.DataContentType)
	if event.SpecVersion == "" {
		event.SpecVersion = "1.0"
	}
	if event.DataContentType == "" {
		event.DataContentType = "application/json"
	}
	if event.ID == "" {
		return fmt.Errorf("missing id")
	}
	if event.Source == "" {
		return fmt.Errorf("missing source")
	}
	if event.Type == "" {
		return fmt.Errorf("missing type")
	}
	if !supportedEventTypes[event.Type] {
		return fmt.Errorf("unsupported type %q", event.Type)
	}
	if event.Time == "" {
		event.Time = time.Now().UTC().Format(time.RFC3339)
	}
	if _, err := time.Parse(time.RFC3339, event.Time); err != nil {
		return fmt.Errorf("invalid time %q", event.Time)
	}
	if event.Data == nil {
		event.Data = map[string]interface{}{}
	}
	return nil
}

func sampleEvents() []Event {
	return []Event{
		{
			SpecVersion:     "1.0",
			ID:              "evt-promotion-001",
			Source:          "tryops://controller/promotion",
			Type:            "tryops.promotion.decision",
			Subject:         "model/vton-catvton-2026-06-11-001",
			Time:            "2026-06-11T00:00:00Z",
			DataContentType: "application/json",
			TenantID:        "demo-tenant",
			Actor:           "risk_reviewer",
			Data: map[string]interface{}{
				"candidate_id": "vton-catvton-2026-06-11-001",
				"approved":     true,
				"stage":        "champion",
			},
		},
		{
			SpecVersion:     "1.0",
			ID:              "evt-feedback-001",
			Source:          "tryops://console/feedback",
			Type:            "tryops.feedback.created",
			Subject:         "request/req-native-job-runner-llm",
			Time:            "2026-06-11T00:00:01Z",
			DataContentType: "application/json",
			TenantID:        "demo-tenant",
			Actor:           "viewer",
			Data: map[string]interface{}{
				"rating": 5,
				"label":  "useful",
			},
		},
		{
			SpecVersion:     "1.0",
			ID:              "evt-incident-001",
			Source:          "tryops://console/incident",
			Type:            "tryops.incident.updated",
			Subject:         "incident/bad-candidate-drill",
			Time:            "2026-06-11T00:00:02Z",
			DataContentType: "application/json",
			TenantID:        "demo-tenant",
			Actor:           "operator",
			Data: map[string]interface{}{
				"status":   "blocked",
				"severity": "high",
			},
		},
		{
			SpecVersion:     "1.0",
			ID:              "evt-quota-001",
			Source:          "tryops://gateway/quota",
			Type:            "tryops.quota.decision",
			Subject:         "tenant/demo-tenant",
			Time:            "2026-06-11T00:00:03Z",
			DataContentType: "application/json",
			TenantID:        "demo-tenant",
			Actor:           "tryops-gateway",
			Data: map[string]interface{}{
				"workload": "llm",
				"allowed":  true,
				"plan":     "enterprise",
			},
		},
	}
}
