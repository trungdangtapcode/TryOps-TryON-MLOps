package main

import "testing"

func TestParseNPMAudit(t *testing.T) {
	payload := []byte(`{"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":1,"high":0,"critical":0,"total":1}}}`)
	vulns, err := parseNPMAudit(payload)
	if err != nil {
		t.Fatalf("parseNPMAudit returned error: %v", err)
	}
	if vulns["moderate"] != 1 || vulns["total"] != 1 {
		t.Fatalf("unexpected vulnerability map: %#v", vulns)
	}
}

func TestBuildReportMarksMissingRequiredTools(t *testing.T) {
	report := buildReport(
		[]toolStatus{
			{Name: "trivy", Required: true, Available: false},
			{Name: "npm", Available: true},
		},
		[]scanResult{{Name: "web_npm_audit", Tool: "npm", Passed: true}},
	)
	if !report.Passed {
		t.Fatal("expected installed scan to pass")
	}
	if report.ProductionReady {
		t.Fatal("expected production readiness to remain false with missing required tools")
	}
	if len(report.MissingRequiredTools) != 1 || report.MissingRequiredTools[0] != "trivy" {
		t.Fatalf("unexpected missing tools: %#v", report.MissingRequiredTools)
	}
}
