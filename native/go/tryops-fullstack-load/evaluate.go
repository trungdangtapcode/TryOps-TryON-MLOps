package main

import (
	"context"
	"fmt"
	"time"
)

func RunFullStackLoad(cfg Config) (Report, error) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	python, err := startPythonAPI(ctx, cfg)
	if err != nil {
		return Report{}, err
	}
	defer python.Stop()
	gateway, err := startGateway(ctx, cfg)
	if err != nil {
		return Report{}, err
	}
	defer gateway.Stop()

	baseURL := fmt.Sprintf("http://127.0.0.1:%d", cfg.GatewayPort)
	specs := buildScenarios(baseURL, cfg)
	scenarioResults := make([]ScenarioResult, 0, len(specs))
	for _, spec := range specs {
		RunLoad(spec, minInt(8, cfg.Requests), minInt(2, cfg.Concurrency))
		result := RunLoad(spec, weightedRequests(cfg.Requests, spec.Weight), cfg.Concurrency)
		slo := evaluateSLO(result, spec, cfg)
		scenarioResults = append(scenarioResults, ScenarioResult{
			Name:    spec.Name,
			Method:  spec.Method,
			Path:    scenarioPath(spec),
			Weight:  spec.Weight,
			Load:    result,
			SLO:     slo,
			Headers: redactedHeaders(spec.Headers),
		})
	}
	tools := detectExternalTools(cfg.RequireExternal)
	summary := summarizeReport(scenarioResults, tools)
	passed := summary.PassedScenarios == summary.TotalScenarios && externalGatePassed(tools)
	return Report{
		SchemaVersion: "tryops.native_fullstack_load.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339Nano),
		Passed:        passed,
		CoverageLevel: "native_go_fullstack_gateway_bff_load_slo",
		Driver: map[string]string{
			"name":     "tryops-fullstack-load",
			"language": "go",
			"version":  "0.1.0",
		},
		Load: map[string]int{
			"base_requests_per_scenario": cfg.Requests,
			"concurrency":                cfg.Concurrency,
		},
		Summary:       summary,
		Scenarios:     scenarioResults,
		ExternalTools: tools,
		Research: []map[string]string{
			{"name": "k6", "url": "https://k6.io/docs/", "use": "optional open-source load-test confirmation tool"},
			{"name": "Locust", "url": "https://docs.locust.io/", "use": "optional Python ecosystem load-test confirmation tool"},
			{"name": "Go net/http", "url": "https://pkg.go.dev/net/http", "use": "native load driver and keep-alive HTTP clients"},
		},
		Notes: []string{
			"The executed gate uses a compiled Go load driver to avoid Python/GIL load-generator bias.",
			"The driver starts FastAPI and the Rust gateway locally, then drives Console/product traffic through /api/*.",
			"k6 and locust availability is recorded for external confirmation; set --require-external to fail when neither is installed.",
		},
	}, nil
}

func summarizeReport(results []ScenarioResult, tools []ExternalTool) Summary {
	summary := Summary{TotalScenarios: len(results), ExternalReady: externalAvailable(tools)}
	minRPS := 0.0
	for _, result := range results {
		if result.SLO.Passed {
			summary.PassedScenarios++
		}
		summary.TotalRequests += result.Load.Requests
		summary.TotalErrors += result.Load.Errors
		if result.Load.LatencyMs.P95 > summary.WorstP95MS {
			summary.WorstP95MS = result.Load.LatencyMs.P95
		}
		if result.Load.LatencyMs.P99 > summary.WorstP99MS {
			summary.WorstP99MS = result.Load.LatencyMs.P99
		}
		if minRPS == 0 || result.Load.RequestsPerSec < minRPS {
			minRPS = result.Load.RequestsPerSec
		}
	}
	summary.MinRPS = round2(minRPS)
	summary.WorstP95MS = round4(summary.WorstP95MS)
	summary.WorstP99MS = round4(summary.WorstP99MS)
	return summary
}

func weightedRequests(base int, weight int) int {
	if base < 1 {
		base = 1
	}
	if weight < 1 {
		weight = 1
	}
	return base * weight
}

func redactedHeaders(headers map[string]string) map[string]string {
	if len(headers) == 0 {
		return nil
	}
	out := make(map[string]string, len(headers))
	for key, value := range headers {
		if key == "authorization" || key == "x-api-key" {
			out[key] = "<redacted>"
		} else {
			out[key] = value
		}
	}
	return out
}

func minInt(left int, right int) int {
	if left < right {
		return left
	}
	return right
}
