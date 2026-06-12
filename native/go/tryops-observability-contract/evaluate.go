package main

import (
	"fmt"
	"time"
)

func evaluate(cfg Config) (Report, error) {
	checks := []Check{}
	collector, err := evaluateCollector(cfg.Root, cfg.CollectorPath, &checks)
	if err != nil {
		return Report{}, err
	}
	compose, err := evaluateCompose(cfg.Root, cfg.ComposePath, &checks)
	if err != nil {
		return Report{}, err
	}
	prometheus, err := evaluatePrometheus(cfg.Root, cfg.PrometheusPath, &checks)
	if err != nil {
		return Report{}, err
	}
	correlation, err := evaluateCorrelation(cfg, &checks)
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
	coverage := cfg.CoverageLevel
	if coverage == "" {
		coverage = "partial"
	}
	return Report{
		SchemaVersion:   schemaVersion,
		GeneratedAt:     time.Now().UTC().Format(time.RFC3339),
		Passed:          failedChecks == 0,
		ProductionReady: cfg.ProductionReady,
		CoverageLevel:   coverage,
		Research:        researchSources(),
		Collector:       collector,
		Compose:         compose,
		Prometheus:      prometheus,
		Correlation:     correlation,
		Summary: ReportSummary{
			PassedChecks:       passedChecks,
			FailedChecks:       failedChecks,
			TotalChecks:        len(checks),
			CollectorPipelines: len(collector.Pipelines),
			CorrelatedTraces:   len(correlation.SharedTraceIDs),
			StructuredLogs:     correlation.APILogs + correlation.GatewayLogs,
		},
		Checks: checks,
		Notes: []string{
			fmt.Sprintf("Research refreshed on %s against OpenTelemetry Collector configuration and Logs Data Model docs.", cfg.ResearchRefresh),
			"This is native contract evidence for collector wiring and correlation. Full production readiness still requires live OTLP export from every service under sustained load.",
		},
	}, nil
}

func addCheck(checks *[]Check, name string, passed bool, detail string) {
	if detail == "" {
		detail = "not configured"
	}
	*checks = append(*checks, Check{Name: name, Passed: passed, Detail: detail})
}

func researchSources() []ResearchSource {
	return []ResearchSource{
		{
			Name: "OpenTelemetry Collector configuration",
			URL:  "https://opentelemetry.io/docs/collector/configuration/",
			Use:  "receivers, processors, exporters, extensions, and service pipelines",
		},
		{
			Name: "OpenTelemetry Logs Data Model",
			URL:  "https://opentelemetry.io/docs/specs/otel/logs/data-model/",
			Use:  "trace/span correlation fields, severity, resource, and attributes",
		},
		{
			Name: "OpenTelemetry Collector Contrib filelog receiver",
			URL:  "https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/filelogreceiver",
			Use:  "JSONL structured-log ingestion into the collector",
		},
	}
}
