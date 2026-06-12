package main

import (
	"flag"
	"os"
	"strconv"
	"strings"
)

func parseConfig() Config {
	cfg := Config{}
	flag.IntVar(&cfg.Requests, "requests", envInt("TRYOPS_FULLSTACK_LOAD_REQUESTS", 96), "requests per scenario")
	flag.IntVar(&cfg.Concurrency, "concurrency", envInt("TRYOPS_FULLSTACK_LOAD_CONCURRENCY", 8), "parallel workers per scenario")
	flag.StringVar(&cfg.GatewayBin, "gateway-bin", getenv("TRYOPS_FULLSTACK_LOAD_GATEWAY_BIN", "artifacts/native/tryops-gateway"), "compiled Rust gateway binary")
	flag.StringVar(&cfg.PythonBin, "python-bin", getenv("TRYOPS_FULLSTACK_LOAD_PYTHON_BIN", "python"), "Python executable used to start uvicorn")
	flag.IntVar(&cfg.GatewayPort, "gateway-port", envInt("TRYOPS_FULLSTACK_LOAD_GATEWAY_PORT", 18221), "Rust gateway port")
	flag.IntVar(&cfg.PythonPort, "python-port", envInt("TRYOPS_FULLSTACK_LOAD_PYTHON_PORT", 18222), "FastAPI/uvicorn port")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_FULLSTACK_LOAD_OUTPUT", "artifacts/eval/load/native_fullstack_load.json"), "JSON report output path")
	flag.BoolVar(&cfg.RequireExternal, "require-external", envBool("TRYOPS_FULLSTACK_LOAD_REQUIRE_EXTERNAL", false), "fail when neither k6 nor locust is installed")
	flag.Float64Var(&cfg.MaxErrorRate, "max-error-rate", envFloat("TRYOPS_FULLSTACK_LOAD_MAX_ERROR_RATE", 0), "maximum allowed scenario error rate")
	flag.Float64Var(&cfg.DefaultMaxP95MS, "max-p95-ms", envFloat("TRYOPS_FULLSTACK_LOAD_MAX_P95_MS", 2500), "default p95 latency SLO")
	flag.Float64Var(&cfg.DefaultMaxP99MS, "max-p99-ms", envFloat("TRYOPS_FULLSTACK_LOAD_MAX_P99_MS", 5000), "default p99 latency SLO")
	flag.Float64Var(&cfg.DefaultMinRPS, "min-rps", envFloat("TRYOPS_FULLSTACK_LOAD_MIN_RPS", 1), "default minimum requests/sec")
	flag.Parse()
	if cfg.Requests < 1 {
		cfg.Requests = 1
	}
	if cfg.Concurrency < 1 {
		cfg.Concurrency = 1
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
	value, err := strconv.Atoi(getenv(key, ""))
	if err != nil {
		return fallback
	}
	return value
}

func envFloat(key string, fallback float64) float64 {
	value, err := strconv.ParseFloat(getenv(key, ""), 64)
	if err != nil {
		return fallback
	}
	return value
}

func envBool(key string, fallback bool) bool {
	switch strings.ToLower(getenv(key, "")) {
	case "1", "true", "yes", "y":
		return true
	case "0", "false", "no", "n":
		return false
	default:
		return fallback
	}
}
