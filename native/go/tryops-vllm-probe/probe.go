package main

import (
	"context"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

func runProbe(ctx context.Context, cfg Config) Report {
	report := Report{
		SchemaVersion: "tryops.vllm_serving_probe.v1",
		CreatedAt:     time.Now().UTC().Format(time.RFC3339Nano),
		Status:        "skipped",
		Driver: DriverInfo{
			Name:     "tryops-vllm-probe",
			Language: "go",
			Version:  "0.1.0",
		},
		Target: TargetInfo{
			BaseURL:     cfg.BaseURL,
			MetricsURL:  cfg.MetricsURL,
			Model:       cfg.Model,
			Prompt:      cfg.Prompt,
			MaxTokens:   cfg.MaxTokens,
			Requests:    cfg.Requests,
			Concurrency: cfg.Concurrency,
		},
		Environment: inspectEnvironment(ctx),
		Research: map[string]string{
			"vllm_openai_server": "https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html",
			"vllm_quickstart":    "https://docs.vllm.ai/en/stable/getting_started/quickstart.html",
		},
	}
	client := &http.Client{Timeout: cfg.RequestTimeout}

	modelsURL := cfg.BaseURL + "/models"
	models, check, err := fetchModels(ctx, client, cfg, modelsURL)
	report.Checks = append(report.Checks, check)
	if err != nil {
		report.Status = "skipped"
		report.Reasons = append(report.Reasons, "vLLM OpenAI-compatible endpoint is not reachable: "+err.Error())
		report.Metrics = fetchMetrics(ctx, client, cfg)
		return report
	}
	report.Models = models
	if !models.Available {
		report.Status = "failed"
		report.Reasons = append(report.Reasons, "models endpoint responded but no model ids were returned")
		report.Metrics = fetchMetrics(ctx, client, cfg)
		return report
	}

	selected := cfg.Model
	if selected == "" {
		selected = models.Selected
		report.Target.Model = selected
	}
	chat := runChat(ctx, client, cfg, selected)
	report.Chat = chat
	report.Checks = append(report.Checks, CheckResult{
		Name:       "chat_completions",
		Passed:     chat.Passed,
		StatusCode: chat.StatusCode,
		LatencyMS:  chat.LatencyMS,
		Error:      chat.Error,
		Detail:     "POST /chat/completions",
	})
	if !chat.Passed {
		report.Status = "failed"
		report.Reasons = append(report.Reasons, "chat completion probe failed")
		report.Metrics = fetchMetrics(ctx, client, cfg)
		return report
	}

	report.Load = runLoad(ctx, client, cfg, selected)
	report.Metrics = fetchMetrics(ctx, client, cfg)
	if report.Load.Failed > 0 {
		report.Status = "failed"
		report.Reasons = append(report.Reasons, "load probe had failed requests")
		return report
	}
	report.Status = "passed"
	report.Passed = true
	return report
}

func fetchModels(ctx context.Context, client *http.Client, cfg Config, url string) (ModelsResult, CheckResult, error) {
	result, err := getJSON(ctx, client, url, cfg.APIKey)
	check := CheckResult{
		Name:       "models",
		LatencyMS:  ms(result.Latency),
		StatusCode: result.StatusCode,
		Detail:     "GET /models",
	}
	if err != nil {
		check.Error = err.Error()
		return ModelsResult{}, check, err
	}
	check.ResponseSize = len(result.Body)
	if result.StatusCode != http.StatusOK {
		check.Error = fmt.Sprintf("unexpected status %d", result.StatusCode)
		return ModelsResult{}, check, fmt.Errorf(check.Error)
	}
	ids := modelIDs(result.Data)
	selected := ""
	if len(ids) > 0 {
		selected = ids[0]
	}
	if cfg.Model != "" {
		for _, id := range ids {
			if id == cfg.Model {
				selected = id
				break
			}
		}
	}
	check.Passed = len(ids) > 0
	return ModelsResult{Available: len(ids) > 0, ModelIDs: ids, Selected: selected}, check, nil
}

func runChat(ctx context.Context, client *http.Client, cfg Config, model string) ChatResult {
	return runChatPrompt(ctx, client, cfg, model, cfg.Prompt)
}

func runChatPrompt(ctx context.Context, client *http.Client, cfg Config, model string, prompt string) ChatResult {
	payload := chatPayload(model, prompt, cfg.MaxTokens)
	result, err := postJSON(ctx, client, cfg.BaseURL+"/chat/completions", cfg.APIKey, payload)
	chat := ChatResult{Attempted: true, LatencyMS: ms(result.Latency), StatusCode: result.StatusCode}
	if err != nil {
		chat.Error = err.Error()
		return chat
	}
	if result.StatusCode != http.StatusOK {
		chat.Error = fmt.Sprintf("unexpected status %d", result.StatusCode)
		return chat
	}
	chat.Passed = true
	fillUsage(result.Data, &chat.PromptTokens, &chat.CompletionTokens, &chat.TotalTokens)
	chat.ResponsePreview = previewText(firstAssistantText(result.Data), 240)
	return chat
}

func runLoad(ctx context.Context, client *http.Client, cfg Config, model string) LoadResult {
	load := LoadResult{Attempted: true, Requests: cfg.Requests, Concurrency: cfg.Concurrency}
	start := time.Now()
	jobs := make(chan int)
	var mu sync.Mutex
	latencies := make([]float64, 0, cfg.Requests)
	for worker := 0; worker < cfg.Concurrency; worker++ {
		go func() {
			for index := range jobs {
				prompt := fmt.Sprintf("%s [probe_request=%d]", cfg.Prompt, index)
				result := runChatPrompt(ctx, client, cfg, model, prompt)
				mu.Lock()
				if result.Passed {
					load.Succeeded++
					load.CompletionTokens += result.CompletionTokens
					latencies = append(latencies, result.LatencyMS)
				} else {
					load.Failed++
					if load.FirstFailureReason == "" {
						load.FirstFailureReason = result.Error
					}
				}
				mu.Unlock()
			}
		}()
	}
	for i := 0; i < cfg.Requests; i++ {
		select {
		case <-ctx.Done():
			load.Failed += cfg.Requests - i
			load.FirstFailureReason = ctx.Err().Error()
			close(jobs)
			load.WallClockSeconds = time.Since(start).Seconds()
			return load
		case jobs <- i:
		}
	}
	close(jobs)
	for {
		mu.Lock()
		done := load.Succeeded+load.Failed >= cfg.Requests
		mu.Unlock()
		if done {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	load.WallClockSeconds = time.Since(start).Seconds()
	sort.Float64s(latencies)
	load.LatencyP50MS = percentile(latencies, 0.50)
	load.LatencyP95MS = percentile(latencies, 0.95)
	if len(latencies) > 0 {
		load.LatencyMaxMS = latencies[len(latencies)-1]
	}
	if load.WallClockSeconds > 0 {
		load.TokensPerSecond = float64(load.CompletionTokens) / load.WallClockSeconds
	}
	return load
}

func fetchMetrics(ctx context.Context, client *http.Client, cfg Config) MetricsResult {
	result, err := getText(ctx, client, cfg.MetricsURL, cfg.APIKey)
	metrics := MetricsResult{Attempted: true, LatencyMS: ms(result.Latency), StatusCode: result.StatusCode}
	if err != nil {
		metrics.Error = err.Error()
		return metrics
	}
	if result.StatusCode != http.StatusOK {
		metrics.Error = fmt.Sprintf("unexpected status %d", result.StatusCode)
		return metrics
	}
	body := string(result.Body)
	metrics.Available = true
	metrics.ContainsVLLMMetrics = strings.Contains(body, "vllm:")
	metrics.SampleMetricNames = sampleMetricNames(body, 8)
	return metrics
}

func chatPayload(model string, prompt string, maxTokens int) map[string]interface{} {
	return map[string]interface{}{
		"model": model,
		"messages": []map[string]string{
			{"role": "user", "content": prompt},
		},
		"temperature": 0,
		"max_tokens":  maxTokens,
	}
}
