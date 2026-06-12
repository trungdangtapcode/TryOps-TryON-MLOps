package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
)

type QuotaClient struct {
	http *http.Client
}

func newQuotaClient(cfg Config) QuotaClient {
	return QuotaClient{http: &http.Client{Timeout: cfg.Timeout}}
}

func (client QuotaClient) submit(ctx context.Context, gatewayURL string, request QuotaRequest) (int, QuotaDecision, error) {
	body, err := json.Marshal(request)
	if err != nil {
		return 0, QuotaDecision{}, fmt.Errorf("marshal request: %w", err)
	}
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, gatewayURL+"/v1/quota/check", bytes.NewReader(body))
	if err != nil {
		return 0, QuotaDecision{}, fmt.Errorf("build request: %w", err)
	}
	httpRequest.Header.Set("Content-Type", "application/json")
	response, err := client.http.Do(httpRequest)
	if err != nil {
		return 0, QuotaDecision{}, err
	}
	defer response.Body.Close()
	var decision QuotaDecision
	if err := json.NewDecoder(response.Body).Decode(&decision); err != nil {
		return response.StatusCode, decision, fmt.Errorf("decode response: %w", err)
	}
	if response.StatusCode != http.StatusOK {
		return response.StatusCode, decision, fmt.Errorf("unexpected status %d", response.StatusCode)
	}
	return response.StatusCode, decision, nil
}
