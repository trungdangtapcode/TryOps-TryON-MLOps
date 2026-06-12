package main

import (
	"flag"
	"fmt"
	"strings"
	"time"
)

type Config struct {
	GatewayURLs     []string
	OutputPath      string
	Requests        int
	ExpectedAllowed int
	Concurrency     int
	UserID          string
	Plan            string
	Workload        string
	Period          string
	EstimatedTokens int
	Timeout         time.Duration
}

func parseConfig(args []string) (Config, error) {
	var urls string
	var timeoutSeconds int
	cfg := Config{}
	fs := flag.NewFlagSet("tryops-distributed-quota", flag.ContinueOnError)
	fs.StringVar(&urls, "gateway-urls", "http://127.0.0.1:18101,http://127.0.0.1:18102", "comma-separated Rust gateway base URLs")
	fs.StringVar(&cfg.OutputPath, "output", "artifacts/eval/quota/native_distributed_quota_admission.json", "JSON report output path")
	fs.IntVar(&cfg.Requests, "requests", 32, "total concurrent quota requests")
	fs.IntVar(&cfg.ExpectedAllowed, "expected-allowed", 20, "expected cluster-wide allowed requests")
	fs.IntVar(&cfg.Concurrency, "concurrency", 16, "concurrent workers")
	fs.StringVar(&cfg.UserID, "user-id", "distributed-quota-user", "quota user id")
	fs.StringVar(&cfg.Plan, "plan", "free", "quota plan")
	fs.StringVar(&cfg.Workload, "workload", "llm", "quota workload")
	fs.StringVar(&cfg.Period, "period", "2026-06-12", "quota period")
	fs.IntVar(&cfg.EstimatedTokens, "estimated-tokens", 1, "tokens charged per request")
	fs.IntVar(&timeoutSeconds, "timeout-seconds", 5, "HTTP timeout seconds")
	if err := fs.Parse(args); err != nil {
		return cfg, err
	}
	for _, raw := range strings.Split(urls, ",") {
		url := strings.TrimRight(strings.TrimSpace(raw), "/")
		if url != "" {
			cfg.GatewayURLs = append(cfg.GatewayURLs, url)
		}
	}
	if len(cfg.GatewayURLs) == 0 {
		return cfg, fmt.Errorf("at least one gateway URL is required")
	}
	if cfg.Requests <= 0 {
		return cfg, fmt.Errorf("requests must be positive")
	}
	if cfg.ExpectedAllowed <= 0 {
		return cfg, fmt.Errorf("expected-allowed must be positive")
	}
	if cfg.Concurrency <= 0 {
		cfg.Concurrency = 1
	}
	if timeoutSeconds <= 0 {
		timeoutSeconds = 5
	}
	cfg.Timeout = time.Duration(timeoutSeconds) * time.Second
	return cfg, nil
}
