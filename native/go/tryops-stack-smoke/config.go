package main

import (
	"flag"
	"os"
	"strings"
	"time"
)

type config struct {
	GatewayURL    string
	GuardrailURL  string
	PrometheusURL string
	GrafanaURL    string
	MinIOURL      string
	MLflowURL     string
	OutputPath    string
	Timeout       time.Duration
	Retries       int
}

func parseConfig() config {
	cfg := config{}
	flag.StringVar(&cfg.GatewayURL, "gateway-url", getenv("TRYOPS_STACK_GATEWAY_URL", "http://127.0.0.1:8081"), "Rust gateway base URL")
	flag.StringVar(&cfg.GuardrailURL, "guardrail-url", getenv("TRYOPS_STACK_GUARDRAIL_URL", "http://127.0.0.1:18083"), "Go guardrail base URL")
	flag.StringVar(&cfg.PrometheusURL, "prometheus-url", getenv("TRYOPS_STACK_PROMETHEUS_URL", "http://127.0.0.1:9090"), "Prometheus base URL")
	flag.StringVar(&cfg.GrafanaURL, "grafana-url", getenv("TRYOPS_STACK_GRAFANA_URL", "http://127.0.0.1:3000"), "Grafana base URL")
	flag.StringVar(&cfg.MinIOURL, "minio-url", getenv("TRYOPS_STACK_MINIO_URL", "http://127.0.0.1:9000"), "MinIO base URL")
	flag.StringVar(&cfg.MLflowURL, "mlflow-url", getenv("TRYOPS_STACK_MLFLOW_URL", "http://127.0.0.1:5000"), "MLflow base URL")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_STACK_SMOKE_OUTPUT", "artifacts/eval/full_stack/full_stack_smoke.json"), "JSON report output path")
	flag.DurationVar(&cfg.Timeout, "timeout", 90*time.Second, "total retry window per check")
	flag.IntVar(&cfg.Retries, "retries", 30, "maximum attempts per check")
	flag.Parse()
	cfg.GatewayURL = trimSlash(cfg.GatewayURL)
	cfg.GuardrailURL = trimSlash(cfg.GuardrailURL)
	cfg.PrometheusURL = trimSlash(cfg.PrometheusURL)
	cfg.GrafanaURL = trimSlash(cfg.GrafanaURL)
	cfg.MinIOURL = trimSlash(cfg.MinIOURL)
	cfg.MLflowURL = trimSlash(cfg.MLflowURL)
	return cfg
}

func getenv(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func trimSlash(value string) string {
	return strings.TrimRight(strings.TrimSpace(value), "/")
}
