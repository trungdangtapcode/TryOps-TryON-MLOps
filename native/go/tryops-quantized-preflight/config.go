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
	OutputPath     string
	Python         string
	Timeout        time.Duration
	RequestTimeout time.Duration
	Candidates     []CandidateSpec
}

func parseConfig() Config {
	cfg := Config{}
	repos := ""
	flag.StringVar(&cfg.BaseURL, "base-url", getenv("TRYOPS_HF_BASE_URL", "https://huggingface.co"), "Hugging Face-compatible base URL")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_QUANTIZED_PREFLIGHT_OUTPUT", "artifacts/eval/llm_quantized/quantized_model_preflight.json"), "JSON report output path")
	flag.StringVar(&cfg.Python, "python", getenv("TRYOPS_PYTHON", "python"), "Python executable for runtime package detection")
	flag.StringVar(&repos, "candidates", getenv("TRYOPS_QUANTIZED_CANDIDATES", defaultCandidates()), "comma-separated method=repo entries")
	flag.DurationVar(&cfg.Timeout, "timeout", envDuration("TRYOPS_QUANTIZED_PREFLIGHT_TIMEOUT", 2*time.Minute), "total preflight timeout")
	flag.DurationVar(&cfg.RequestTimeout, "request-timeout", envDuration("TRYOPS_QUANTIZED_PREFLIGHT_REQUEST_TIMEOUT", 20*time.Second), "per-request timeout")
	flag.Parse()
	cfg.BaseURL = trimSlash(cfg.BaseURL)
	cfg.Candidates = parseCandidates(repos)
	return cfg
}

func defaultCandidates() string {
	return strings.Join([]string{
		"gptq=Qwen/Qwen2.5-0.5B-Instruct-GPTQ-Int4",
		"awq=Qwen/Qwen2.5-0.5B-Instruct-AWQ",
	}, ",")
}

func parseCandidates(value string) []CandidateSpec {
	parts := strings.Split(value, ",")
	specs := make([]CandidateSpec, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		pair := strings.SplitN(part, "=", 2)
		if len(pair) != 2 {
			continue
		}
		method := strings.ToLower(strings.TrimSpace(pair[0]))
		repo := strings.Trim(strings.TrimSpace(pair[1]), "/")
		if method == "" || repo == "" {
			continue
		}
		specs = append(specs, CandidateSpec{Method: method, Repo: repo})
	}
	return specs
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

func trimSlash(value string) string {
	return strings.TrimRight(strings.TrimSpace(value), "/")
}
