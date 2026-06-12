package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestEvaluateAlertmanagerContract(t *testing.T) {
	root := t.TempDir()
	writeFixture(t, root, "infra/alertmanager/alertmanager.yml", `
route:
  receiver: tryops-ticket-log
  group_by: [alertname, workload, severity]
  routes:
    - receiver: tryops-page-webhook
      matchers: ['severity="page"']
    - receiver: tryops-ticket-log
      matchers: ['severity=~"warning|ticket"']
receivers:
  - name: tryops-ticket-log
  - name: tryops-page-webhook
    webhook_configs:
      - url: http://controller:18082/alerts/webhook
        send_resolved: true
inhibit_rules:
  - source_matchers: ['severity="page"']
    target_matchers: ['severity=~"warning|ticket"']
    equal: [workload, alertname]
`)
	writeFixture(t, root, "infra/prometheus/prometheus.yml", `
rule_files:
  - infra/prometheus/tryops_alerts.yml
  - infra/prometheus/tryops_burn_rate_alerts.yml
  - infra/prometheus/tryops_finops_alerts.yml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]
scrape_configs:
  - job_name: tryops-api
`)
	writeFixture(t, root, "infra/prometheus/tryops_alerts.yml", alertRulesFixture())
	writeFixture(t, root, "infra/prometheus/tryops_burn_rate_alerts.yml", burnRulesFixture())
	writeFixture(t, root, "infra/prometheus/tryops_finops_alerts.yml", finopsRulesFixture())
	writeFixture(t, root, "docker-compose.yml", `
services:
  prometheus:
    image: prom/prometheus:latest
    depends_on:
      alertmanager:
        condition: service_started
  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "${TRYOPS_ALERTMANAGER_PORT:-9093}:9093"
    volumes:
      - ./infra/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    healthcheck:
      test: ["CMD", "amtool", "check-config", "/etc/alertmanager/alertmanager.yml"]
`)
	report, err := evaluate(Config{
		Root:             root,
		AlertmanagerPath: "infra/alertmanager/alertmanager.yml",
		PrometheusPath:   "infra/prometheus/prometheus.yml",
		ComposePath:      "docker-compose.yml",
	})
	if err != nil {
		t.Fatal(err)
	}
	if !report.Passed {
		t.Fatalf("expected pass: %#v", report.Checks)
	}
	if report.Summary.AlertRules != 10 || report.Summary.PageReceivers != 1 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func writeFixture(t *testing.T, root string, path string, content string) {
	t.Helper()
	fullPath := filepath.Join(root, path)
	if err := os.MkdirAll(filepath.Dir(fullPath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(fullPath, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func alertRulesFixture() string {
	return `groups:
- name: tryops-enterprise-alerts
  rules:
  - alert: TryOpsLLMLatencyRegression
    expr: tryops_llm_latency_p95_ms > 100
    labels: {severity: warning, workload: llm}
    annotations: {runbook_url: docs/observability_contract.md}
  - alert: TryOpsVTONLatencyRegression
    expr: tryops_vton_latency_ms > 5000
    labels: {severity: warning, workload: vton}
    annotations: {runbook_url: docs/observability_contract.md}
  - alert: TryOpsLLMQualityRegression
    expr: tryops_llm_quality_score < 0.95
    labels: {severity: page, workload: llm}
    annotations: {runbook_url: docs/observability_contract.md}
  - alert: TryOpsVTONQualityRegression
    expr: tryops_vton_garment_similarity < 0.8
    labels: {severity: page, workload: vton}
    annotations: {runbook_url: docs/observability_contract.md}
`
}

func burnRulesFixture() string {
	return `groups:
- name: tryops-slo-burn-rate-alerts
  rules:
  - alert: TryOpsLlmPageFastBurnRate
    expr: vector(1)
    labels: {severity: page, workload: llm}
    annotations: {runbook_url: docs/service_level_objectives.md}
  - alert: TryOpsVtonPageFastBurnRate
    expr: vector(1)
    labels: {severity: page, workload: vton}
    annotations: {runbook_url: docs/service_level_objectives.md}
  - alert: TryOpsControlPlaneTicketBurnRate
    expr: vector(1)
    labels: {severity: ticket, workload: control_plane}
    annotations: {runbook_url: docs/service_level_objectives.md}
`
}

func finopsRulesFixture() string {
	return `groups:
- name: tryops-finops-alerts
  rules:
  - alert: TryOpsTenantBudgetWarning
    expr: vector(1)
    labels: {severity: warning, workload: finops}
    annotations: {runbook_url: docs/finops_semantic_cache.md}
  - alert: TryOpsTenantBudgetHardLimit
    expr: vector(1)
    labels: {severity: page, workload: finops}
    annotations: {runbook_url: docs/finops_semantic_cache.md}
  - alert: TryOpsSemanticCacheHitRateLow
    expr: vector(1)
    labels: {severity: warning, workload: llm}
    annotations: {runbook_url: docs/finops_semantic_cache.md}
`
}
