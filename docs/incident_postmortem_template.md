# {{TITLE}}

Incident ID: {{INCIDENT_ID}}
Severity: {{SEVERITY}}
Status: {{STATUS}}
Workload: {{WORKLOAD}}
Owner: {{OWNER}}
Created: {{CREATED_AT}}
Resolved: {{RESOLVED_AT}}

## Summary

The incident workflow was triggered by alert {{ALERT_NAMES}} and linked to fingerprint `{{ERROR_FINGERPRINT}}`.

## Impact

The affected workload was `{{WORKLOAD}}`. User impact is bounded by the drill evidence and the rollback state attached below.

## Detection

Alertmanager routed the alert to the Go controller webhook and attached the runbook `{{RUNBOOK_URL}}`.

## Timeline

{{TIMELINE}}

## Root Cause

The controlled bad-candidate drill crossed the error-budget burn threshold before the candidate could be promoted.

## Mitigation

Rollback package `{{ROLLBACK_PACKAGE_ID}}` restored `{{RESTORED_CANDIDATE_ID}}` after rolling back `{{ROLLED_BACK_CANDIDATE_ID}}`.

## Follow-up Actions

{{FOLLOW_UP_ACTIONS}}

## Evidence

- Native incident workflow: `artifacts/eval/incidents/native_incident_workflow.json`
- Rollback state: `artifacts/deployments/rollback_state.json`
