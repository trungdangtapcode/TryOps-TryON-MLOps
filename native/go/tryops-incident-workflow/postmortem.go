package main

import (
	"fmt"
	"strings"
)

var requiredPostmortemSections = []string{
	"## Summary",
	"## Impact",
	"## Detection",
	"## Timeline",
	"## Root Cause",
	"## Mitigation",
	"## Follow-up Actions",
	"## Evidence",
}

func renderPostmortem(root string, cfg Config, incident IncidentSummary, alert AlertSummary, rollback RollbackSummary, timeline []TimelineStep) (string, PostmortemSummary, error) {
	template, err := readText(root, cfg.TemplatePath)
	if err != nil {
		template = defaultPostmortemTemplate()
	}
	timelineLines := make([]string, 0, len(timeline))
	for _, step := range timeline {
		timelineLines = append(timelineLines, fmt.Sprintf("- %02d `%s`: %s (%s)", step.Order, step.State, step.Description, step.Status))
	}
	actionItems := []string{
		"- [ ] Wire external GlitchTip/Sentry-compatible DSN for production error ingestion.",
		"- [ ] Add browser incident timeline controls after the local artifact path is stable.",
		"- [ ] Run a live Alertmanager webhook smoke against the Go controller in the production profile.",
	}
	replacements := map[string]string{
		"{{INCIDENT_ID}}":              incident.ID,
		"{{TITLE}}":                    incident.Title,
		"{{SEVERITY}}":                 incident.Severity,
		"{{STATUS}}":                   incident.Status,
		"{{WORKLOAD}}":                 incident.Workload,
		"{{OWNER}}":                    incident.Owner,
		"{{CREATED_AT}}":               incident.CreatedAt,
		"{{RESOLVED_AT}}":              incident.ResolvedAt,
		"{{ERROR_FINGERPRINT}}":        incident.ErrorFingerprint,
		"{{ALERT_NAMES}}":              strings.Join(alert.AlertNames, ", "),
		"{{RUNBOOK_URL}}":              alert.RunbookURL,
		"{{ROLLBACK_PACKAGE_ID}}":      rollback.PackageID,
		"{{RESTORED_CANDIDATE_ID}}":    rollback.RestoredCandidateID,
		"{{ROLLED_BACK_CANDIDATE_ID}}": rollback.RolledBackCandidateID,
		"{{TIMELINE}}":                 strings.Join(timelineLines, "\n"),
		"{{FOLLOW_UP_ACTIONS}}":        strings.Join(actionItems, "\n"),
	}
	body := template
	for token, value := range replacements {
		body = strings.ReplaceAll(body, token, value)
	}
	summary := PostmortemSummary{
		Path:             cfg.PostmortemPath,
		TemplatePath:     cfg.TemplatePath,
		RequiredSections: requiredPostmortemSections,
		ActionItems:      len(actionItems),
		Written:          false,
	}
	return body, summary, nil
}

func validatePostmortem(markdown string) []string {
	var failures []string
	for _, section := range requiredPostmortemSections {
		if !strings.Contains(markdown, section) {
			failures = append(failures, "missing section "+section)
		}
	}
	if !strings.Contains(markdown, "- [ ]") {
		failures = append(failures, "missing follow-up action checkbox")
	}
	return failures
}

func defaultPostmortemTemplate() string {
	return `# {{TITLE}}

Incident ID: {{INCIDENT_ID}}
Severity: {{SEVERITY}}
Status: {{STATUS}}
Workload: {{WORKLOAD}}
Owner: {{OWNER}}
Created: {{CREATED_AT}}
Resolved: {{RESOLVED_AT}}

## Summary

The bad-candidate drill generated alert {{ALERT_NAMES}}, opened an incident workflow, and restored the previous champion.

## Impact

The simulated impact is limited to the VTON production-demo lane and is represented by fingerprint {{ERROR_FINGERPRINT}}.

## Detection

Alertmanager routed the page alert to the Go controller webhook. Runbook: {{RUNBOOK_URL}}.

## Timeline

{{TIMELINE}}

## Root Cause

The candidate failed rollout safety gates and crossed the error-budget burn threshold during the controlled drill.

## Mitigation

Rollback package {{ROLLBACK_PACKAGE_ID}} restored {{RESTORED_CANDIDATE_ID}} after rolling back {{ROLLED_BACK_CANDIDATE_ID}}.

## Follow-up Actions

{{FOLLOW_UP_ACTIONS}}

## Evidence

- Native incident workflow: artifacts/eval/incidents/native_incident_workflow.json
- Rollback state: artifacts/deployments/rollback_state.json
`
}
