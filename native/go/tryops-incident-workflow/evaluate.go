package main

import (
	"fmt"
	"time"
)

func evaluateWorkflow(cfg Config) (Report, string, error) {
	generatedAt := cfg.GeneratedAt
	if generatedAt == "" {
		generatedAt = time.Now().UTC().Format(time.RFC3339)
	}
	alertPayload := sampleAlertPayload(generatedAt)
	alert := summarizeAlert(alertPayload)
	errorEvent := buildErrorEvent(generatedAt, alert)
	errorTracking := summarizeErrorTracking(errorEvent)
	rollback, rollbackErr := loadRollbackSummary(cfg.RootPath, cfg.RollbackPath)

	incident := IncidentSummary{
		ID:                 "inc-bad-candidate-drill",
		Title:              "Bad VTON candidate rollback drill",
		Severity:           alert.Severity,
		Status:             "resolved",
		Workload:           alert.Workload,
		Owner:              "mlops-operator",
		Source:             "alertmanager",
		CreatedAt:          generatedAt,
		ResolvedAt:         generatedAt,
		ErrorFingerprint:   errorEvent.Fingerprint,
		ImpactedComponents: []string{"tryops-api", "tryops-gateway", "vton-production-demo"},
		RollbackRequired:   true,
		PostmortemPath:     cfg.PostmortemPath,
	}
	timeline := buildTimeline(alert, rollback, cfg)
	markdown, postmortem, postmortemErr := renderPostmortem(cfg.RootPath, cfg, incident, alert, rollback, timeline)

	checks := []Check{
		controllerAlertWebhookReady(cfg.RootPath, cfg.ControllerPath),
		dispatcherIncidentEventCheck(cfg.RootPath, cfg.DispatcherPath),
		checkFromFailures("alertmanager_payload_valid", validateAlertPayload(alertPayload), "Alertmanager payload has receiver, status, labels, runbook, and alert entries"),
		checkFromFailures("error_event_otel_shape", validateErrorEvent(errorEvent), "local error event has OTel-style trace/span/service/severity/exception fields"),
		rollbackCheck(rollback, rollbackErr),
	}
	if postmortemErr != nil {
		checks = append(checks, Check{Name: "postmortem_template_rendered", Passed: false, Detail: postmortemErr.Error()})
	} else {
		checks = append(checks, checkFromFailures("postmortem_template_rendered", validatePostmortem(markdown), "postmortem contains required sections and action items"))
	}
	checks = append(checks, checkTimeline(timeline))

	passedChecks, failedChecks := countChecks(checks)
	passed := failedChecks == 0
	if passed {
		outputPostmortem := joinRoot(cfg.RootPath, cfg.PostmortemPath)
		if err := writeText(outputPostmortem, markdown); err != nil {
			checks = append(checks, Check{Name: "postmortem_written", Passed: false, Detail: err.Error()})
			passedChecks, failedChecks = countChecks(checks)
			passed = false
		} else {
			postmortem.Written = true
			checks = append(checks, Check{Name: "postmortem_written", Passed: true, Detail: "wrote " + cfg.PostmortemPath})
			passedChecks, failedChecks = countChecks(checks)
		}
	}

	productionReady := passed && errorTracking.ExternalTracker.Configured
	coverage := "native_incident_workflow_local_contract"
	if productionReady {
		coverage = "native_incident_workflow_external_tracker_ready"
	}
	report := Report{
		SchemaVersion:   schemaVersion,
		GeneratedAt:     generatedAt,
		Passed:          passed,
		ProductionReady: productionReady,
		CoverageLevel:   coverage,
		Incident:        incident,
		Alertmanager:    alert,
		ErrorTracking:   errorTracking,
		Rollback:        rollback,
		Postmortem:      postmortem,
		Timeline:        timeline,
		Checks:          checks,
		Research:        researchRefs(),
		Notes: []string{
			"Local workflow evidence is deterministic and native-first.",
			"Production readiness remains false until an external open-source error tracker DSN is configured and exercised.",
		},
		Summary: ReportSummary{
			PassedChecks:     passedChecks,
			FailedChecks:     failedChecks,
			TotalChecks:      len(checks),
			TimelineSteps:    len(timeline),
			ErrorEvents:      errorTracking.EventCount,
			PostmortemReady:  postmortem.Written,
			ExternalTracking: errorTracking.ExternalTracker.Configured,
		},
	}
	report.Evidence = evidenceRefs(report, cfg)
	return report, markdown, nil
}

func buildTimeline(alert AlertSummary, rollback RollbackSummary, cfg Config) []TimelineStep {
	return []TimelineStep{
		{
			Order:       1,
			State:       "detected",
			Status:      "complete",
			Owner:       "alertmanager",
			Evidence:    []string{"infra/prometheus/tryops_burn_rate_alerts.yml", "infra/alertmanager/alertmanager.yml"},
			Description: fmt.Sprintf("%s fired for %s with %d alert(s)", alert.Severity, alert.Workload, alert.AlertCount),
		},
		{
			Order:       2,
			State:       "triaged",
			Status:      "complete",
			Owner:       "go-controller",
			Evidence:    []string{"native/go/tryops-controller/promotion.go", "native/go/tryops-controller/server.go"},
			Description: "controller accepts Alertmanager webhook and opens incident review",
		},
		{
			Order:       3,
			State:       "mitigated",
			Status:      "complete",
			Owner:       "mlops-operator",
			Evidence:    []string{cfg.RollbackPath},
			Description: fmt.Sprintf("rollback restored %s from package %s", rollback.RestoredCandidateID, rollback.PackageID),
		},
		{
			Order:       4,
			State:       "postmortem_drafted",
			Status:      "complete",
			Owner:       "mlops-operator",
			Evidence:    []string{cfg.PostmortemPath, cfg.TemplatePath},
			Description: "postmortem draft generated with impact, timeline, root cause, mitigation, and follow-up sections",
		},
		{
			Order:       5,
			State:       "resolved",
			Status:      "complete",
			Owner:       "incident-commander",
			Evidence:    []string{"artifacts/eval/events/native_event_dispatcher_report.json", cfg.OutputPath},
			Description: "incident update is ready for audit/webhook dispatch",
		},
	}
}

func checkFromFailures(name string, failures []string, success string) Check {
	if len(failures) > 0 {
		return Check{Name: name, Passed: false, Detail: joinFailures(failures)}
	}
	return Check{Name: name, Passed: true, Detail: success}
}

func checkTimeline(timeline []TimelineStep) Check {
	expected := []string{"detected", "triaged", "mitigated", "postmortem_drafted", "resolved"}
	if len(timeline) != len(expected) {
		return Check{Name: "incident_timeline_complete", Passed: false, Detail: "timeline has unexpected number of steps"}
	}
	for index, state := range expected {
		if timeline[index].State != state || timeline[index].Status != "complete" {
			return Check{Name: "incident_timeline_complete", Passed: false, Detail: "timeline state " + state + " is incomplete"}
		}
	}
	return Check{Name: "incident_timeline_complete", Passed: true, Detail: "detected -> triaged -> mitigated -> postmortem_drafted -> resolved"}
}

func countChecks(checks []Check) (int, int) {
	passed := 0
	failed := 0
	for _, check := range checks {
		if check.Passed {
			passed++
		} else {
			failed++
		}
	}
	return passed, failed
}
