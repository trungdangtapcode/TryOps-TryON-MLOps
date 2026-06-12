package main

import (
	"flag"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	BaseURL        string
	MetricsURL     string
	Model          string
	Prompt         string
	APIKey         string
	OutputPath     string
	Requests       int
	Concurrency    int
	MaxTokens      int
	RequestTimeout time.Duration
	TotalTimeout   time.Duration
	RequireLive    bool
}

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.BaseURL, "base-url", getenv("TRYOPS_VLLM_BASE_URL", "http://127.0.0.1:8000/v1"), "vLLM OpenAI-compatible base URL")
	flag.StringVar(&cfg.MetricsURL, "metrics-url", getenv("TRYOPS_VLLM_METRICS_URL", ""), "vLLM Prometheus metrics URL; defaults to base-url root /metrics")
	flag.StringVar(&cfg.Model, "model", getenv("TRYOPS_VLLM_MODEL", "HuggingFaceTB/SmolLM2-135M-Instruct"), "model id to request")
	flag.StringVar(&cfg.Prompt, "prompt", getenv("TRYOPS_VLLM_PROMPT", "Explain TryOps MLOps in one sentence."), "probe prompt")
	flag.StringVar(&cfg.APIKey, "api-key", getenv("TRYOPS_VLLM_API_KEY", ""), "optional OpenAI-compatible bearer token")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_VLLM_OUTPUT", "artifacts/eval/llm_vllm/vllm_serving_probe.json"), "JSON report output path")
	flag.IntVar(&cfg.Requests, "requests", envInt("TRYOPS_VLLM_REQUESTS", 8), "load probe request count")
	flag.IntVar(&cfg.Concurrency, "concurrency", envInt("TRYOPS_VLLM_CONCURRENCY", 4), "load probe concurrency")
	flag.IntVar(&cfg.MaxTokens, "max-tokens", envInt("TRYOPS_VLLM_MAX_TOKENS", 32), "max completion tokens per request")
	flag.DurationVar(&cfg.RequestTimeout, "request-timeout", envDuration("TRYOPS_VLLM_REQUEST_TIMEOUT", 30*time.Second), "per-request timeout")
	flag.DurationVar(&cfg.TotalTimeout, "timeout", envDuration("TRYOPS_VLLM_TIMEOUT", 2*time.Minute), "total probe timeout")
	flag.BoolVar(&cfg.RequireLive, "require-live", envBool("TRYOPS_VLLM_REQUIRE_LIVE", false), "exit non-zero when no live vLLM-compatible endpoint responds")
	flag.Parse()

	cfg.BaseURL = trimSlash(cfg.BaseURL)
	if cfg.MetricsURL == "" {
		cfg.MetricsURL = metricsURLForBase(cfg.BaseURL)
	} else {
		cfg.MetricsURL = trimSlash(cfg.MetricsURL)
	}
	if cfg.Requests < 1 {
		cfg.Requests = 1
	}
	if cfg.Concurrency < 1 {
		cfg.Concurrency = 1
	}
	if cfg.Concurrency > cfg.Requests {
		cfg.Concurrency = cfg.Requests
	}
	if cfg.MaxTokens < 1 {
		cfg.MaxTokens = 1
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

func envBool(key string, fallback bool) bool {
	value := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
	if value == "" {
		return fallback
	}
	return value == "1" || value == "true" || value == "yes"
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

func trimSlash(value string) string {
	return strings.TrimRight(strings.TrimSpace(value), "/")
}

func metricsURLForBase(base string) string {
	base = trimSlash(base)
	if strings.HasSuffix(base, "/v1") {
		return strings.TrimSuffix(base, "/v1") + "/metrics"
	}
	return base + "/metrics"
}
