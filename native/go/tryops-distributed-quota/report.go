package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

func buildReport(cfg Config, attempts []Attempt, generatedAt time.Time) Report {
	summary := ReportSummary{
		Gateways:      len(cfg.GatewayURLs),
		Requests:      len(attempts),
		ExpectedAllow: cfg.ExpectedAllowed,
	}
	seenGateways := map[string]bool{}
	for _, attempt := range attempts {
		seenGateways[attempt.GatewayURL] = true
		if attempt.Error != "" {
			summary.Errors++
			continue
		}
		if attempt.Allowed {
			summary.Allowed++
		} else {
			summary.Rejected++
		}
	}
	checks := map[string]bool{
		"all_requests_completed":        summary.Errors == 0 && summary.Requests == cfg.Requests,
		"multiple_gateways_exercised":   len(seenGateways) == len(cfg.GatewayURLs) && len(cfg.GatewayURLs) > 1,
		"allowed_equals_global_limit":   summary.Allowed == cfg.ExpectedAllowed,
		"rejected_after_global_limit":   summary.Rejected == cfg.Requests-cfg.ExpectedAllowed,
		"no_cluster_quota_oversell":     summary.Allowed <= cfg.ExpectedAllowed,
		"all_statuses_successful_http":  allStatusesOK(attempts),
		"concurrent_pressure_exercised": cfg.Concurrency > 1 && cfg.Requests > cfg.ExpectedAllowed,
	}
	passed := true
	for _, ok := range checks {
		if !ok {
			passed = false
			break
		}
	}
	return Report{
		SchemaVersion: "tryops.distributed_quota_admission.v1",
		GeneratedAt:   generatedAt.UTC().Format(time.RFC3339),
		Passed:        passed,
		CoverageLevel: "native_rust_postgres_distributed_quota_admission",
		Research: []ResearchLink{
			{
				Name: "PostgreSQL explicit row locking",
				URL:  "https://www.postgresql.org/docs/current/explicit-locking.html",
				Use:  "SELECT FOR UPDATE locks shared quota rows during admission",
			},
			{
				Name: "PostgreSQL transaction isolation",
				URL:  "https://www.postgresql.org/docs/current/transaction-iso.html",
				Use:  "transaction boundaries define the atomic admission unit",
			},
			{
				Name: "Valkey INCR counter pattern",
				URL:  "https://valkey.io/commands/incr/",
				Use:  "Valkey remains a hot counter mirror for admitted usage",
			},
		},
		Config: ReportConfig{
			GatewayURLs:     append([]string{}, cfg.GatewayURLs...),
			Requests:        cfg.Requests,
			ExpectedAllowed: cfg.ExpectedAllowed,
			Concurrency:     cfg.Concurrency,
			Plan:            cfg.Plan,
			Workload:        cfg.Workload,
			Period:          cfg.Period,
		},
		Summary:  summary,
		Checks:   checks,
		Attempts: attempts,
	}
}

func allStatusesOK(attempts []Attempt) bool {
	for _, attempt := range attempts {
		if attempt.StatusCode != 200 || attempt.Error != "" {
			return false
		}
	}
	return true
}

func writeReport(path string, report Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	body, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	body = append(body, '\n')
	return os.WriteFile(path, body, 0o644)
}
