package main

import "net/http"

func buildJobSpecs(cfg config) []jobSpec {
	return []jobSpec{
		{
			Name:        "llm_direct_generation",
			Workload:    "llm",
			Method:      http.MethodPost,
			Path:        "/api/llm/generate",
			Payload:     buildLLMPayload(cfg),
			Timeout:     cfg.JobTimeout,
			MaxAttempts: cfg.RetryAttempts,
			Retry:       retryPolicy{BaseDelay: cfg.RetryBaseDelay},
		},
		{
			Name:        "vton_async_generation",
			Workload:    "vton",
			Method:      http.MethodPost,
			Path:        "/api/vton/jobs",
			Payload:     buildVTONPayload(cfg),
			Timeout:     cfg.JobTimeout,
			MaxAttempts: cfg.RetryAttempts,
			Retry:       retryPolicy{BaseDelay: cfg.RetryBaseDelay},
			Poll: &pollSpec{
				PathPrefix: "/api/vton/jobs",
				Timeout:    cfg.PollTimeout,
				Interval:   cfg.PollInterval,
			},
		},
	}
}

func buildLLMPayload(cfg config) map[string]interface{} {
	return map[string]interface{}{
		"request_id":               "req-native-job-runner-llm",
		"prompt":                   "Explain TryOps native job execution in one concise enterprise sentence.",
		"model_alias":              "baseline",
		"max_tokens":               64,
		"structured":               true,
		"routing_mode":             "direct",
		"canary_percent":           0,
		"shadow":                   false,
		"optimized_available":      false,
		"fallback_enabled":         true,
		"semantic_cache_enabled":   true,
		"semantic_cache_threshold": 0.72,
		"user_id":                  cfg.UserID,
		"quota_plan":               cfg.QuotaPlan,
		"timeout_ms":               int(cfg.JobTimeout / 1e6),
	}
}

func buildVTONPayload(cfg config) map[string]interface{} {
	return map[string]interface{}{
		"request_id":         "req-native-job-runner-vton",
		"model_alias":        "baseline",
		"person_image_path":  cfg.PersonImagePath,
		"garment_image_path": cfg.GarmentImagePath,
		"output_image_path":  cfg.VTONOutputPath,
		"cache_dir":          "artifacts/cache/vton_preflight",
		"routing_mode":       "direct",
		"canary_percent":     0,
		"user_id":            cfg.UserID,
		"quota_plan":         cfg.QuotaPlan,
		"timeout_ms":         int(cfg.JobTimeout / 1e6),
	}
}
