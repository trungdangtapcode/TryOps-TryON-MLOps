package main

import (
	"flag"
	"os"
	"strconv"
	"strings"
	"time"
)

type config struct {
	BaseURL          string
	OutputPath       string
	TotalTimeout     time.Duration
	JobTimeout       time.Duration
	PollTimeout      time.Duration
	PollInterval     time.Duration
	RetryAttempts    int
	RetryBaseDelay   time.Duration
	UserID           string
	QuotaPlan        string
	PersonImagePath  string
	GarmentImagePath string
	VTONOutputPath   string
}

func parseConfig() config {
	cfg := config{}
	flag.StringVar(&cfg.BaseURL, "base-url", getenv("TRYOPS_JOB_RUNNER_BASE_URL", "http://127.0.0.1:8081"), "Rust gateway base URL")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_JOB_RUNNER_OUTPUT", "artifacts/eval/jobs/native_job_runner_report.json"), "JSON report output path")
	flag.DurationVar(&cfg.TotalTimeout, "timeout", envDuration("TRYOPS_JOB_RUNNER_TIMEOUT", 3*time.Minute), "total runner timeout")
	flag.DurationVar(&cfg.JobTimeout, "job-timeout", envDuration("TRYOPS_JOB_RUNNER_JOB_TIMEOUT", 20*time.Second), "deadline for each HTTP attempt")
	flag.DurationVar(&cfg.PollTimeout, "poll-timeout", envDuration("TRYOPS_JOB_RUNNER_POLL_TIMEOUT", 90*time.Second), "deadline for async job polling")
	flag.DurationVar(&cfg.PollInterval, "poll-interval", envDuration("TRYOPS_JOB_RUNNER_POLL_INTERVAL", 500*time.Millisecond), "async job polling interval")
	flag.IntVar(&cfg.RetryAttempts, "attempts", envInt("TRYOPS_JOB_RUNNER_ATTEMPTS", 3), "maximum attempts for transient job submission failures")
	flag.DurationVar(&cfg.RetryBaseDelay, "retry-base-delay", envDuration("TRYOPS_JOB_RUNNER_RETRY_BASE_DELAY", 250*time.Millisecond), "base delay for retry backoff")
	flag.StringVar(&cfg.UserID, "user-id", getenv("TRYOPS_JOB_RUNNER_USER_ID", "native-job-runner"), "user id submitted to quota-aware APIs")
	flag.StringVar(&cfg.QuotaPlan, "quota-plan", getenv("TRYOPS_JOB_RUNNER_QUOTA_PLAN", "enterprise"), "quota plan submitted to quota-aware APIs")
	flag.StringVar(&cfg.PersonImagePath, "person-image", getenv("TRYOPS_JOB_RUNNER_PERSON_IMAGE", "artifacts/demo/vton/person.png"), "local VTON person image path")
	flag.StringVar(&cfg.GarmentImagePath, "garment-image", getenv("TRYOPS_JOB_RUNNER_GARMENT_IMAGE", "artifacts/demo/vton/garment.png"), "local VTON garment image path")
	flag.StringVar(&cfg.VTONOutputPath, "vton-output", getenv("TRYOPS_JOB_RUNNER_VTON_OUTPUT", "artifacts/runtime/vton/native_job_runner_output.png"), "local VTON output image path")
	flag.Parse()

	cfg.BaseURL = trimSlash(cfg.BaseURL)
	if cfg.RetryAttempts < 1 {
		cfg.RetryAttempts = 1
	}
	if cfg.PollInterval <= 0 {
		cfg.PollInterval = 500 * time.Millisecond
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

func trimSlash(value string) string {
	return strings.TrimRight(strings.TrimSpace(value), "/")
}
