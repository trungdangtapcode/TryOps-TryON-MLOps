package main

import (
	"context"
	"io"
	"net/http"
	"strings"
	"time"
)

func runCheck(ctx context.Context, client *http.Client, check smokeCheck, maxAttempts int) checkResult {
	started := time.Now()
	result := checkResult{
		Name:   check.Name,
		URL:    check.URL,
		Method: check.Method,
	}

	if maxAttempts < 1 {
		maxAttempts = 1
	}
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		result.Attempts = attempt
		status, body, err := doRequest(ctx, client, check)
		result.StatusCode = status
		result.Error = ""
		result.Missing = nil
		if err != nil {
			result.Error = err.Error()
		} else if status != check.WantStatus {
			result.Error = http.StatusText(status)
		} else {
			result.Missing = missingSubstrings(body, check.WantContains)
			if len(result.Missing) == 0 {
				result.Passed = true
				result.DurationMS = time.Since(started).Milliseconds()
				return result
			}
			result.Error = "response body missing expected content"
		}

		select {
		case <-ctx.Done():
			result.Error = ctx.Err().Error()
			result.DurationMS = time.Since(started).Milliseconds()
			return result
		case <-time.After(retryDelay(attempt)):
		}
	}
	result.DurationMS = time.Since(started).Milliseconds()
	return result
}

func doRequest(ctx context.Context, client *http.Client, check smokeCheck) (int, string, error) {
	var body io.Reader
	if check.Body != "" {
		body = strings.NewReader(check.Body)
	}
	request, err := http.NewRequestWithContext(ctx, check.Method, check.URL, body)
	if err != nil {
		return 0, "", err
	}
	if check.ContentType != "" {
		request.Header.Set("Content-Type", check.ContentType)
	}
	for name, value := range check.Headers {
		request.Header.Set(name, value)
	}
	response, err := client.Do(request)
	if err != nil {
		return 0, "", err
	}
	defer response.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(response.Body, 2*1024*1024))
	if err != nil {
		return response.StatusCode, "", err
	}
	return response.StatusCode, string(responseBody), nil
}

func missingSubstrings(body string, expected []string) []string {
	var missing []string
	for _, item := range expected {
		if !strings.Contains(body, item) {
			missing = append(missing, item)
		}
	}
	return missing
}

func retryDelay(attempt int) time.Duration {
	delay := time.Duration(250*attempt) * time.Millisecond
	if delay > 3*time.Second {
		return 3 * time.Second
	}
	return delay
}
