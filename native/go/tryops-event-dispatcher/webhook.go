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

func dispatchWebhooks(ctx context.Context, client *http.Client, cfg config, events []Event) map[string]eventResult {
	results := map[string]eventResult{}
	if cfg.WebhookURL == "" {
		for _, event := range events {
			results[event.ID] = eventResult{EventID: event.ID, Type: event.Type, Subject: event.Subject}
		}
		return results
	}
	for _, event := range events {
		results[event.ID] = dispatchWebhook(ctx, client, cfg, event)
	}
	return results
}

func dispatchWebhook(ctx context.Context, client *http.Client, cfg config, event Event) eventResult {
	result := eventResult{EventID: event.ID, Type: event.Type, Subject: event.Subject}
	body, err := json.Marshal(event)
	if err != nil {
		result.Errors = append(result.Errors, err.Error())
		return result
	}
	for attempt := 1; attempt <= cfg.Retries; attempt++ {
		result.Attempts = attempt
		status, err := postWebhook(ctx, client, cfg, event, body)
		result.WebhookStatus = status
		if err == nil && status >= 200 && status < 300 {
			result.WebhookSent = true
			return result
		}
		if err != nil {
			result.Errors = append(result.Errors, err.Error())
		} else {
			result.Errors = append(result.Errors, fmt.Sprintf("webhook status %d", status))
		}
		if attempt < cfg.Retries {
			if err := sleepContext(ctx, cfg.RetryDelay*time.Duration(attempt)); err != nil {
				result.Errors = append(result.Errors, err.Error())
				return result
			}
		}
	}
	return result
}

func postWebhook(ctx context.Context, client *http.Client, cfg config, event Event, body []byte) (int, error) {
	timestamp := time.Now().UTC().Format(time.RFC3339)
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, cfg.WebhookURL, bytes.NewReader(body))
	if err != nil {
		return 0, err
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-TryOps-Event-ID", event.ID)
	request.Header.Set("X-TryOps-Event-Type", event.Type)
	request.Header.Set("X-TryOps-Webhook-Timestamp", timestamp)
	request.Header.Set("X-TryOps-Signature-256", signPayload(cfg.WebhookSecret, timestamp, body))
	response, err := client.Do(request)
	if err != nil {
		return 0, err
	}
	defer response.Body.Close()
	io.Copy(io.Discard, io.LimitReader(response.Body, 1024))
	return response.StatusCode, nil
}

func sleepContext(ctx context.Context, delay time.Duration) error {
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}
