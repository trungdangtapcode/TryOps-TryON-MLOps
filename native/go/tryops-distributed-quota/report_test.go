package main

import (
	"testing"
	"time"
)

func TestBuildReportPassesWhenClusterLimitIsExact(t *testing.T) {
	cfg := Config{
		GatewayURLs:     []string{"http://a", "http://b"},
		Requests:        4,
		ExpectedAllowed: 2,
		Concurrency:     4,
		Plan:            "free",
		Workload:        "llm",
		Period:          "2026-06-12",
	}
	attempts := []Attempt{
		{Index: 0, GatewayURL: "http://a", StatusCode: 200, Allowed: true},
		{Index: 1, GatewayURL: "http://b", StatusCode: 200, Allowed: true},
		{Index: 2, GatewayURL: "http://a", StatusCode: 200, Allowed: false},
		{Index: 3, GatewayURL: "http://b", StatusCode: 200, Allowed: false},
	}

	report := buildReport(cfg, attempts, time.Unix(0, 0))

	if !report.Passed {
		t.Fatalf("expected passing report: %#v", report.Checks)
	}
	if report.Summary.Allowed != 2 || report.Summary.Rejected != 2 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func TestBuildReportRejectsQuotaOversell(t *testing.T) {
	cfg := Config{
		GatewayURLs:     []string{"http://a", "http://b"},
		Requests:        4,
		ExpectedAllowed: 2,
		Concurrency:     4,
		Plan:            "free",
		Workload:        "llm",
		Period:          "2026-06-12",
	}
	attempts := []Attempt{
		{Index: 0, GatewayURL: "http://a", StatusCode: 200, Allowed: true},
		{Index: 1, GatewayURL: "http://b", StatusCode: 200, Allowed: true},
		{Index: 2, GatewayURL: "http://a", StatusCode: 200, Allowed: true},
		{Index: 3, GatewayURL: "http://b", StatusCode: 200, Allowed: false},
	}

	report := buildReport(cfg, attempts, time.Unix(0, 0))

	if report.Passed {
		t.Fatalf("expected quota oversell to fail")
	}
	if report.Checks["no_cluster_quota_oversell"] {
		t.Fatalf("oversell check should fail")
	}
}
