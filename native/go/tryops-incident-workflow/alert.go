package main

import (
	"fmt"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

func sampleAlertPayload(generatedAt string) AlertmanagerPayload {
	return AlertmanagerPayload{
		Receiver: "tryops-page",
		Status:   "firing",
		GroupLabels: map[string]string{
			"alertname": "TryOpsErrorBudgetBurnHigh",
			"severity":  "page",
			"workload":  "vton",
		},
		CommonLabels: map[string]string{
			"alertname": "TryOpsErrorBudgetBurnHigh",
			"severity":  "page",
			"workload":  "vton",
			"service":   "tryops-api",
		},
		Alerts: []AlertmanagerAlert{
			{
				Status: "firing",
				Labels: map[string]string{
					"alertname": "TryOpsErrorBudgetBurnHigh",
					"severity":  "page",
					"workload":  "vton",
					"service":   "tryops-api",
				},
				Annotations: map[string]string{
					"summary":     "VTON error-budget burn crossed the page threshold during the bad-candidate drill.",
					"runbook_url": "docs/rollback_fallback.md",
				},
				StartsAt:     generatedAt,
				GeneratorURL: "http://prometheus:9090/graph?g0.expr=tryops_error_budget_burn_rate",
				Fingerprint:  "tryops-vton-error-budget-page",
			},
		},
		ExternalURL: "http://alertmanager:9093",
		Version:     "4",
		GroupKey:    "{}:{alertname=\"TryOpsErrorBudgetBurnHigh\", workload=\"vton\"}",
	}
}

func validateAlertPayload(payload AlertmanagerPayload) []string {
	var failures []string
	if strings.TrimSpace(payload.Receiver) == "" {
		failures = append(failures, "receiver is required")
	}
	if payload.Status != "firing" && payload.Status != "resolved" {
		failures = append(failures, "status must be firing or resolved")
	}
	if len(payload.Alerts) == 0 {
		failures = append(failures, "at least one alert is required")
	}
	if firstLabel(payload, "severity") == "" {
		failures = append(failures, "severity label is required")
	}
	if firstLabel(payload, "workload") == "" {
		failures = append(failures, "workload label is required")
	}
	for index, alert := range payload.Alerts {
		if alert.Labels["alertname"] == "" {
			failures = append(failures, "alert "+strconv.Itoa(index)+" missing alertname")
		}
		if alert.Labels["severity"] == "" {
			failures = append(failures, "alert "+strconv.Itoa(index)+" missing severity")
		}
		if alert.Labels["workload"] == "" {
			failures = append(failures, "alert "+strconv.Itoa(index)+" missing workload")
		}
		if alert.Annotations["runbook_url"] == "" {
			failures = append(failures, "alert "+strconv.Itoa(index)+" missing runbook_url")
		}
	}
	return failures
}

func summarizeAlert(payload AlertmanagerPayload) AlertSummary {
	names := map[string]bool{}
	runbook := ""
	for _, alert := range payload.Alerts {
		if alert.Labels["alertname"] != "" {
			names[alert.Labels["alertname"]] = true
		}
		if runbook == "" {
			runbook = alert.Annotations["runbook_url"]
		}
	}
	alertNames := make([]string, 0, len(names))
	for name := range names {
		alertNames = append(alertNames, name)
	}
	sort.Strings(alertNames)
	return AlertSummary{
		Receiver:          payload.Receiver,
		Status:            payload.Status,
		Severity:          firstLabel(payload, "severity"),
		Workload:          firstLabel(payload, "workload"),
		AlertNames:        alertNames,
		AlertCount:        len(payload.Alerts),
		RunbookURL:        runbook,
		ControllerWebhook: "/alerts/webhook",
	}
}

func controllerAlertWebhookReady(root string, controllerPath string) Check {
	server, serverErr := readText(root, filepath.Join(controllerPath, "server.go"))
	promotion, promotionErr := readText(root, filepath.Join(controllerPath, "promotion.go"))
	passed := serverErr == nil && promotionErr == nil &&
		strings.Contains(server, "/alerts/webhook") &&
		strings.Contains(promotion, "open incident review")
	detail := "controller registers /alerts/webhook and maps accepted page/ticket alerts to incident review actions"
	if !passed {
		detail = fmt.Sprintf("controller alert path incomplete (server_err=%v promotion_err=%v)", serverErr, promotionErr)
	}
	return Check{Name: "controller_alert_webhook_incident_action", Passed: passed, Detail: detail}
}

func firstLabel(payload AlertmanagerPayload, key string) string {
	for _, labels := range []map[string]string{payload.CommonLabels, payload.GroupLabels} {
		if labels != nil && labels[key] != "" {
			return labels[key]
		}
	}
	for _, alert := range payload.Alerts {
		if alert.Labels[key] != "" {
			return alert.Labels[key]
		}
	}
	return ""
}
