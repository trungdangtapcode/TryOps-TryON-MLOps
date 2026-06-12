package main

import (
	"context"
	"fmt"
	"net/http"
	"time"
)

func RunBenchmark(config BenchmarkConfig) (BenchmarkReport, error) {
	if config.Requests < 1 {
		config.Requests = 1
	}
	if config.Concurrency < 1 {
		config.Concurrency = 1
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	python, err := startPythonAPI(ctx, config)
	if err != nil {
		return BenchmarkReport{}, err
	}
	defer python.Stop()
	gateway, err := startGateway(ctx, config)
	if err != nil {
		return BenchmarkReport{}, err
	}
	defer gateway.Stop()

	gatewayBase := fmt.Sprintf("http://127.0.0.1:%d", config.GatewayPort)
	pythonBase := fmt.Sprintf("http://127.0.0.1:%d", config.PythonPort)

	scenarios := map[string]ScenarioReport{}
	scenarios["health_get"] = runComparisonScenario(
		"Identical GET /health handler; isolates serving runtime overhead.",
		"/health",
		HTTPRequestSpec{Method: http.MethodGet, URL: gatewayBase + "/health", ExpectedStatus: http.StatusOK},
		HTTPRequestSpec{Method: http.MethodGet, URL: pythonBase + "/health", ExpectedStatus: http.StatusOK},
		config,
		nil,
	)
	scenarios["promotion_post_direct"] = runComparisonScenario(
		"Validated POST promotion path on direct service contracts.",
		"/v1/promotion/evaluate",
		HTTPRequestSpec{
			Method:         http.MethodPost,
			URL:            gatewayBase + "/v1/promotion/evaluate",
			Headers:        jsonHeaders(),
			Body:           nativePromotionPayload,
			ExpectedStatus: http.StatusOK,
		},
		HTTPRequestSpec{
			Method:         http.MethodPost,
			URL:            pythonBase + "/v1/promotion/evaluate",
			Headers:        jsonHeaders(),
			Body:           pythonPromotionPayload,
			ExpectedStatus: http.StatusOK,
		},
		config,
		[]string{
			"The Rust gateway direct endpoint measures native preflight admission.",
			"The FastAPI endpoint measures the full Python policy/auth contract with the same promotion outcome.",
		},
	)
	scenarios["promotion_post_edge_proxy"] = runProxyScenario(gatewayBase, pythonBase, config)

	return BenchmarkReport{
		SchemaVersion: "tryops.native_gateway_benchmark.v1",
		CreatedAt:     time.Now().UTC().Format(time.RFC3339Nano),
		Driver: map[string]string{
			"name":     "tryops-go-loadgen",
			"language": "go",
			"version":  "0.1.0",
		},
		Load: map[string]int{
			"requests":    config.Requests,
			"concurrency": config.Concurrency,
		},
		Scenarios: scenarios,
		Notes: []string{
			"Go stdlib load driver avoids the Python/GIL benchmark-driver limitation.",
			"All scenarios warm each target before measuring.",
			"The edge-proxy POST scenario includes Rust gateway preflight/proxy overhead plus the FastAPI policy path.",
		},
	}, nil
}

func runComparisonScenario(
	description string,
	endpoint string,
	nativeSpec HTTPRequestSpec,
	pythonSpec HTTPRequestSpec,
	config BenchmarkConfig,
	notes []string,
) ScenarioReport {
	RunLoad(nativeSpec, 200, minInt(config.Concurrency, 8))
	RunLoad(pythonSpec, 200, minInt(config.Concurrency, 8))
	results := map[string]LoadResult{
		"native_rust_gateway": RunLoad(nativeSpec, config.Requests, config.Concurrency),
		"python_fastapi":      RunLoad(pythonSpec, config.Requests, config.Concurrency),
	}
	return ScenarioReport{
		Description: description,
		Endpoint:    endpoint,
		Results:     results,
		Speedup:     speedup(results["native_rust_gateway"], results["python_fastapi"]),
		Notes:       notes,
	}
}

func runProxyScenario(gatewayBase string, pythonBase string, config BenchmarkConfig) ScenarioReport {
	gatewaySpec := HTTPRequestSpec{
		Method:         http.MethodPost,
		URL:            gatewayBase + "/api/promotion/evaluate",
		Headers:        signedProxyHeaders(),
		Body:           pythonPromotionPayload,
		ExpectedStatus: http.StatusOK,
	}
	pythonSpec := HTTPRequestSpec{
		Method:         http.MethodPost,
		URL:            pythonBase + "/v1/promotion/evaluate",
		Headers:        jsonHeaders(),
		Body:           pythonPromotionPayload,
		ExpectedStatus: http.StatusOK,
	}
	RunLoad(gatewaySpec, 200, minInt(config.Concurrency, 8))
	RunLoad(pythonSpec, 200, minInt(config.Concurrency, 8))
	results := map[string]LoadResult{
		"native_rust_gateway_proxy_to_fastapi": RunLoad(gatewaySpec, config.Requests, config.Concurrency),
		"python_fastapi_direct":                RunLoad(pythonSpec, config.Requests, config.Concurrency),
	}
	return ScenarioReport{
		Description: "Full edge path: Rust gateway signed-artifact preflight and /api/* proxy into FastAPI policy evaluation.",
		Endpoint:    "/api/promotion/evaluate -> /v1/promotion/evaluate",
		Results:     results,
		Speedup:     speedup(results["native_rust_gateway_proxy_to_fastapi"], results["python_fastapi_direct"]),
		Notes: []string{
			"This is expected to be slower than FastAPI direct when the upstream is the same FastAPI process.",
			"It measures the cost of adding the compiled edge boundary in front of the validated POST path.",
		},
	}
}

func speedup(native LoadResult, python LoadResult) *SpeedupReport {
	if native.RequestsPerSec <= 0 || python.RequestsPerSec <= 0 || native.LatencyMs.P99 <= 0 || native.LatencyMs.P50 <= 0 {
		return nil
	}
	return &SpeedupReport{
		ThroughputX: round2(native.RequestsPerSec / python.RequestsPerSec),
		P50LatencyX: round2(python.LatencyMs.P50 / native.LatencyMs.P50),
		P99LatencyX: round2(python.LatencyMs.P99 / native.LatencyMs.P99),
	}
}

func minInt(left int, right int) int {
	if left < right {
		return left
	}
	return right
}
