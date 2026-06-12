package main

import "time"

func evaluate(cfg Config) (Report, error) {
	checks := []Check{}
	alertmanager, err := evaluateAlertmanager(cfg.Root, cfg.AlertmanagerPath, &checks)
	if err != nil {
		return Report{}, err
	}
	prometheus, err := evaluatePrometheus(cfg.Root, cfg.PrometheusPath, &checks)
	if err != nil {
		return Report{}, err
	}
	compose, err := evaluateCompose(cfg.Root, cfg.ComposePath, &checks)
	if err != nil {
		return Report{}, err
	}
	passedChecks := 0
	failedChecks := 0
	for _, check := range checks {
		if check.Passed {
			passedChecks++
		} else {
			failedChecks++
		}
	}
	return Report{
		SchemaVersion: schemaVersion,
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        failedChecks == 0,
		CoverageLevel: "native_alertmanager_routing_contract",
		Research: []ResearchSource{
			{
				Name: "Alertmanager configuration",
				URL:  "https://prometheus.io/docs/alerting/latest/configuration/",
				Use:  "routing tree, receivers, webhook configs, grouping, repeat intervals, and inhibition",
			},
			{
				Name: "Prometheus alerting configuration",
				URL:  "https://prometheus.io/docs/prometheus/latest/configuration/configuration/#alerting",
				Use:  "Prometheus alertmanager target wiring",
			},
			{
				Name: "Prometheus alerting rules",
				URL:  "https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/",
				Use:  "alert rule labels, annotations, runbook links, and routing metadata",
			},
		},
		Alertmanager: alertmanager,
		Prometheus:   prometheus,
		Compose:      compose,
		Summary: ReportSummary{
			PassedChecks:    passedChecks,
			FailedChecks:    failedChecks,
			TotalChecks:     len(checks),
			AlertRules:      prometheus.AlertRuleCount,
			PageReceivers:   countReceiver(alertmanager.Receivers, "tryops-page-webhook"),
			TicketReceivers: countReceiver(alertmanager.Receivers, "tryops-ticket-log"),
		},
		Checks: checks,
		Notes: []string{
			"Alertmanager is wired locally for page/ticket routing, inhibition, and Prometheus forwarding.",
			"External pager, chat, and ticket credentials remain production secret-management work.",
		},
	}, nil
}

func countReceiver(receivers []string, expected string) int {
	count := 0
	for _, receiver := range receivers {
		if receiver == expected {
			count++
		}
	}
	return count
}
