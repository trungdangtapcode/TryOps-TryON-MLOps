package main

import (
	"flag"
	"os"
	"strconv"
	"strings"
	"time"
)

type config struct {
	Mode          string
	EventsPath    string
	AuditLogPath  string
	WebhookURL    string
	WebhookSecret string
	OutputPath    string
	Timeout       time.Duration
	Retries       int
	RetryDelay    time.Duration
}

func parseConfig() config {
	cfg := config{}
	flag.StringVar(&cfg.Mode, "mode", getenv("TRYOPS_EVENT_DISPATCHER_MODE", "dispatch"), "dispatch or sample")
	flag.StringVar(&cfg.EventsPath, "events", getenv("TRYOPS_EVENT_DISPATCHER_EVENTS", ""), "JSON array or JSONL events path")
	flag.StringVar(&cfg.AuditLogPath, "audit-log", getenv("TRYOPS_EVENT_DISPATCHER_AUDIT_LOG", "artifacts/eval/events/native_audit_events.jsonl"), "audit JSONL output path")
	flag.StringVar(&cfg.WebhookURL, "webhook-url", getenv("TRYOPS_EVENT_DISPATCHER_WEBHOOK_URL", ""), "optional signed webhook sink URL")
	flag.StringVar(&cfg.WebhookSecret, "webhook-secret", getenv("TRYOPS_EVENT_DISPATCHER_WEBHOOK_SECRET", "tryops-local-event-webhook"), "HMAC webhook secret")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_EVENT_DISPATCHER_OUTPUT", "artifacts/eval/events/native_event_dispatcher_report.json"), "JSON report output path")
	flag.DurationVar(&cfg.Timeout, "timeout", envDuration("TRYOPS_EVENT_DISPATCHER_TIMEOUT", 30*time.Second), "overall dispatch timeout")
	flag.IntVar(&cfg.Retries, "retries", envInt("TRYOPS_EVENT_DISPATCHER_RETRIES", 3), "webhook delivery attempts per event")
	flag.DurationVar(&cfg.RetryDelay, "retry-delay", envDuration("TRYOPS_EVENT_DISPATCHER_RETRY_DELAY", 100*time.Millisecond), "webhook retry base delay")
	flag.Parse()
	if cfg.Retries < 1 {
		cfg.Retries = 1
	}
	return cfg
}

func getenv(key string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func envDuration(key string, fallback time.Duration) time.Duration {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := time.ParseDuration(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func envInt(key string, fallback int) int {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}
