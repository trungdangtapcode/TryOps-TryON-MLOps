package main

import (
	"fmt"
	"net/http"
	"strings"
)

func buildScenarios(baseURL string, cfg Config) []HTTPRequestSpec {
	base := strings.TrimRight(baseURL, "/")
	return []HTTPRequestSpec{
		{
			Name:           "gateway_health",
			Method:         http.MethodGet,
			URL:            base + "/health",
			ExpectedStatus: http.StatusOK,
			Weight:         8,
			MaxP95MS:       250,
			MaxP99MS:       750,
			MinRPS:         25,
		},
		{
			Name:           "rbac_session_viewer",
			Method:         http.MethodGet,
			URL:            base + "/api/auth/session?api_key=tryops-viewer-demo-key",
			ExpectedStatus: http.StatusOK,
			Weight:         4,
			MaxP95MS:       cfg.DefaultMaxP95MS,
			MaxP99MS:       cfg.DefaultMaxP99MS,
			MinRPS:         cfg.DefaultMinRPS,
		},
		{
			Name:           "evaluation_summary",
			Method:         http.MethodGet,
			URL:            base + "/api/evaluations/summary?api_key=tryops-viewer-demo-key",
			ExpectedStatus: http.StatusOK,
			Weight:         2,
			MaxP95MS:       cfg.DefaultMaxP95MS,
			MaxP99MS:       cfg.DefaultMaxP99MS,
			MinRPS:         cfg.DefaultMinRPS,
		},
		{
			Name:           "quota_summary",
			Method:         http.MethodGet,
			URL:            base + "/api/quota/summary?api_key=tryops-viewer-demo-key",
			ExpectedStatus: http.StatusOK,
			Weight:         2,
			MaxP95MS:       cfg.DefaultMaxP95MS,
			MaxP99MS:       cfg.DefaultMaxP99MS,
			MinRPS:         cfg.DefaultMinRPS,
		},
		{
			Name:           "llm_generate",
			Method:         http.MethodPost,
			URL:            base + "/api/llm/generate",
			Headers:        jsonHeaders(),
			Body:           llmPayload,
			ExpectedStatus: http.StatusOK,
			Weight:         3,
			MaxP95MS:       5000,
			MaxP99MS:       9000,
			MinRPS:         0.25,
		},
		{
			Name:           "promotion_gate_operator",
			Method:         http.MethodPost,
			URL:            base + "/api/promotion/evaluate",
			Headers:        signedHeaders(),
			Body:           promotionPayload,
			ExpectedStatus: http.StatusOK,
			Weight:         2,
			MaxP95MS:       cfg.DefaultMaxP95MS,
			MaxP99MS:       cfg.DefaultMaxP99MS,
			MinRPS:         cfg.DefaultMinRPS,
		},
	}
}

func scenarioPath(spec HTTPRequestSpec) string {
	if index := strings.Index(spec.URL, "/api/"); index >= 0 {
		return spec.URL[index:]
	}
	if index := strings.Index(spec.URL, "/health"); index >= 0 {
		return spec.URL[index:]
	}
	return fmt.Sprintf("%s %s", spec.Method, spec.URL)
}
