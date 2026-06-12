package main

import (
	"flag"
	"path/filepath"
)

func parseConfig() Config {
	var cfg Config
	flag.StringVar(&cfg.Root, "root", ".", "repository root")
	flag.StringVar(&cfg.CollectorPath, "collector", "infra/otel/collector.yml", "OpenTelemetry Collector config path")
	flag.StringVar(&cfg.ComposePath, "compose", "docker-compose.yml", "Docker Compose path")
	flag.StringVar(&cfg.PrometheusPath, "prometheus", "infra/prometheus/prometheus.yml", "Prometheus config path")
	flag.StringVar(&cfg.TraceSamplePath, "trace-sample", "artifacts/eval/traces/trace_sample.json", "trace sample report path")
	flag.StringVar(&cfg.APISpanPath, "api-spans", "artifacts/eval/traces/api_spans.jsonl", "API span JSONL path")
	flag.StringVar(&cfg.APILogPath, "api-logs", "artifacts/eval/traces/api_events.jsonl", "API structured log JSONL path")
	flag.StringVar(&cfg.GatewayLogPath, "gateway-logs", "artifacts/logs/gateway_events.jsonl", "gateway structured log JSONL path")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/observability/native_observability_contract.json", "report output path")
	flag.BoolVar(&cfg.ProductionReady, "production-ready", false, "mark full production readiness when live OTLP exporters are proven")
	flag.StringVar(&cfg.CoverageLevel, "coverage", "partial", "coverage level")
	flag.StringVar(&cfg.ResearchRefresh, "research-refresh", "2026-06-12", "research refresh date")
	flag.Parse()
	cfg.Root = cleanPath(cfg.Root)
	return cfg
}

func resolve(root string, path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}

func rel(root string, path string) string {
	relative, err := filepath.Rel(root, path)
	if err == nil && relative != "." && relative != "" && !startsWithParent(relative) {
		return filepath.ToSlash(relative)
	}
	return filepath.ToSlash(path)
}

func cleanPath(path string) string {
	cleaned, err := filepath.Abs(path)
	if err != nil {
		return filepath.Clean(path)
	}
	return cleaned
}

func startsWithParent(path string) bool {
	return len(path) >= 2 && path[0] == '.' && path[1] == '.'
}
