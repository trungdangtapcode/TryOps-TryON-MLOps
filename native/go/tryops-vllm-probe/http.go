package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const maxBodyBytes = 8 * 1024 * 1024

type httpResult struct {
	StatusCode int
	Headers    http.Header
	Body       []byte
	Data       map[string]interface{}
	Latency    time.Duration
}

func getJSON(ctx context.Context, client *http.Client, url string, apiKey string) (httpResult, error) {
	return doRequest(ctx, client, http.MethodGet, url, apiKey, nil, true)
}

func postJSON(ctx context.Context, client *http.Client, url string, apiKey string, payload map[string]interface{}) (httpResult, error) {
	return doRequest(ctx, client, http.MethodPost, url, apiKey, payload, true)
}

func getText(ctx context.Context, client *http.Client, url string, apiKey string) (httpResult, error) {
	return doRequest(ctx, client, http.MethodGet, url, apiKey, nil, false)
}

func doRequest(ctx context.Context, client *http.Client, method string, url string, apiKey string, payload map[string]interface{}, decodeJSON bool) (httpResult, error) {
	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			return httpResult{}, err
		}
		body = bytes.NewReader(encoded)
	}
	request, err := http.NewRequestWithContext(ctx, method, url, body)
	if err != nil {
		return httpResult{}, err
	}
	request.Header.Set("Accept", "application/json")
	request.Header.Set("X-TryOps-Native-Probe", "go-vllm-probe")
	if payload != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	if apiKey != "" {
		request.Header.Set("Authorization", "Bearer "+apiKey)
	}

	start := time.Now()
	response, err := client.Do(request)
	latency := time.Since(start)
	if err != nil {
		return httpResult{Latency: latency}, err
	}
	defer response.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(response.Body, maxBodyBytes))
	if err != nil {
		return httpResult{StatusCode: response.StatusCode, Headers: response.Header.Clone(), Latency: latency}, err
	}
	result := httpResult{StatusCode: response.StatusCode, Headers: response.Header.Clone(), Body: responseBody, Latency: latency}
	if decodeJSON && len(responseBody) > 0 {
		if err := json.Unmarshal(responseBody, &result.Data); err != nil {
			return result, fmt.Errorf("decode json: %w", err)
		}
	}
	return result, nil
}
