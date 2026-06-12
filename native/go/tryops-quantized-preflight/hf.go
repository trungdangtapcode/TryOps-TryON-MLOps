package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const maxConfigBytes = 4 * 1024 * 1024

type hfConfig struct {
	ModelType          string                 `json:"model_type"`
	Architectures      []string               `json:"architectures"`
	License            string                 `json:"license"`
	QuantizationConfig map[string]interface{} `json:"quantization_config"`
}

func fetchConfig(ctx context.Context, client *http.Client, baseURL string, repo string) (hfConfig, int, int, string, error) {
	configURL := resolveURL(baseURL, repo, "config.json")
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, configURL, nil)
	if err != nil {
		return hfConfig{}, 0, 0, configURL, err
	}
	req.Header.Set("Accept", "application/json")
	response, err := client.Do(req)
	if err != nil {
		return hfConfig{}, 0, 0, configURL, err
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, maxConfigBytes))
	if err != nil {
		return hfConfig{}, response.StatusCode, len(body), configURL, err
	}
	if response.StatusCode != http.StatusOK {
		return hfConfig{}, response.StatusCode, len(body), configURL, fmt.Errorf("unexpected status %d", response.StatusCode)
	}
	config := hfConfig{}
	if err := json.Unmarshal(body, &config); err != nil {
		return hfConfig{}, response.StatusCode, len(body), configURL, err
	}
	return config, response.StatusCode, len(body), configURL, nil
}

func headArtifact(ctx context.Context, client *http.Client, baseURL string, repo string, path string) ArtifactCheck {
	check := ArtifactCheck{Path: path, URL: resolveURL(baseURL, repo, path)}
	req, err := http.NewRequestWithContext(ctx, http.MethodHead, check.URL, nil)
	if err != nil {
		check.Error = err.Error()
		return check
	}
	response, err := client.Do(req)
	if err != nil {
		check.Error = err.Error()
		return check
	}
	defer response.Body.Close()
	check.StatusCode = response.StatusCode
	check.Reachable = response.StatusCode >= 200 && response.StatusCode < 400
	check.ContentLength = response.ContentLength
	if !check.Reachable {
		check.Error = fmt.Sprintf("unexpected status %d", response.StatusCode)
	}
	return check
}

func resolveURL(baseURL string, repo string, path string) string {
	segments := strings.Split(strings.Trim(repo, "/"), "/")
	escaped := make([]string, 0, len(segments)+3)
	for _, segment := range segments {
		escaped = append(escaped, url.PathEscape(segment))
	}
	escaped = append(escaped, "resolve", "main", url.PathEscape(path))
	return strings.TrimRight(baseURL, "/") + "/" + strings.Join(escaped, "/")
}

func clientWithTimeout(timeout time.Duration) *http.Client {
	return &http.Client{Timeout: timeout}
}
