package main

import (
	"fmt"
	"strings"
)

func dispatcherIncidentEventCheck(root string, dispatcherPath string) Check {
	source, err := readText(root, dispatcherPath)
	passed := err == nil && strings.Contains(source, "tryops.incident.updated")
	detail := "event dispatcher supports tryops.incident.updated audit/webhook fanout"
	if !passed {
		detail = fmt.Sprintf("dispatcher incident event support not found: %v", err)
	}
	return Check{Name: "incident_event_dispatcher_supported", Passed: passed, Detail: detail}
}

func evidenceRefs(report Report, cfg Config) []EvidenceRef {
	status := "passed"
	if !report.Passed {
		status = "failed"
	}
	return []EvidenceRef{
		{
			Name:          "incident_workflow",
			Path:          cfg.OutputPath,
			SchemaVersion: schemaVersion,
			Status:        status,
			Detail:        "native Go incident lifecycle, error event, rollback, and postmortem evidence",
		},
		{
			Name:          "rollback_state",
			Path:          cfg.RollbackPath,
			SchemaVersion: "tryops.rollback_state.v1",
			Status:        statusForEvidence(report.Rollback.SchemaVersion == "tryops.rollback_state.v1"),
			Detail:        "latest rollback record linked into the incident timeline",
		},
		{
			Name:   "postmortem",
			Path:   cfg.PostmortemPath,
			Status: statusForEvidence(report.Postmortem.Written),
			Detail: "generated blameless postmortem draft from template",
		},
	}
}

func researchRefs() []ResearchRef {
	return []ResearchRef{
		{
			Name: "OpenTelemetry Logs Data Model",
			URL:  "https://opentelemetry.io/docs/specs/otel/logs/data-model/",
			Use:  "trace/span/service/severity fields for the local error event envelope",
		},
		{
			Name: "OpenTelemetry Exception Semantic Conventions",
			URL:  "https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-spans/",
			Use:  "exception event shape and exception type/message fields",
		},
		{
			Name: "Prometheus Alertmanager Webhook Receiver",
			URL:  "https://prometheus.io/docs/alerting/latest/configuration/#webhook_config",
			Use:  "Alertmanager webhook payload as the incident trigger contract",
		},
		{
			Name: "Google SRE Postmortem Culture",
			URL:  "https://sre.google/sre-book/postmortem-culture/",
			Use:  "blameless postmortem template and follow-up ownership model",
		},
		{
			Name: "GlitchTip Error Tracking",
			URL:  "https://glitchtip.com/documentation/",
			Use:  "optional open-source Sentry-compatible external error tracking DSN",
		},
	}
}

func statusForEvidence(ok bool) string {
	if ok {
		return "passed"
	}
	return "missing"
}

func joinFailures(failures []string) string {
	return strings.Join(failures, "; ")
}
