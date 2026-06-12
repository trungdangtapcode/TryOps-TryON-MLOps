package main

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

func runJobs(ctx context.Context, client *http.Client, cfg config, specs []jobSpec) []jobResult {
	results := make([]jobResult, 0, len(specs))
	for _, spec := range specs {
		results = append(results, runJob(ctx, client, cfg, spec))
	}
	return results
}

func runJob(ctx context.Context, client *http.Client, cfg config, spec jobSpec) jobResult {
	started := time.Now()
	result := jobResult{
		Name:      spec.Name,
		Workload:  spec.Workload,
		Method:    spec.Method,
		Path:      spec.Path,
		Status:    "failed",
		RequestID: requestIDFromPayload(spec.Payload),
	}

	response, err := submitWithRetry(ctx, client, cfg, spec, &result)
	result.DurationMS = time.Since(started).Milliseconds()
	if err != nil {
		result.Error = err.Error()
		return result
	}
	result.HTTPStatus = response.StatusCode
	result.Response = summarizeResponse(response.Data)

	if !successHTTP(response.StatusCode) {
		result.Error = fmt.Sprintf("unexpected HTTP status %d", response.StatusCode)
		return result
	}

	if spec.Poll != nil {
		if err := pollAsyncJob(ctx, client, cfg, spec, &result, response.Data); err != nil {
			result.Error = err.Error()
			result.DurationMS = time.Since(started).Milliseconds()
			return result
		}
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}

	status := lowerField(response.Data, "status")
	if status == "" || status == "completed" || status == "ok" {
		result.Passed = true
		result.Status = "passed"
		return result
	}
	result.Error = fmt.Sprintf("job returned status %q", status)
	return result
}

func submitWithRetry(ctx context.Context, client *http.Client, cfg config, spec jobSpec, result *jobResult) (httpJSONResponse, error) {
	attempts := spec.MaxAttempts
	if attempts < 1 {
		attempts = 1
	}
	var last httpJSONResponse
	var lastErr error
	for attempt := 1; attempt <= attempts; attempt++ {
		result.Attempts = attempt
		requestCtx, cancel := context.WithTimeout(ctx, spec.Timeout)
		response, err := doJSON(requestCtx, client, spec.Method, cfg.BaseURL+spec.Path, spec.Payload)
		cancel()
		last = response
		lastErr = err
		if !retryable(response.StatusCode, err) {
			return response, err
		}
		if attempt == attempts {
			break
		}
		if err := sleepContext(ctx, retryDelay(spec.Retry, attempt)); err != nil {
			return response, err
		}
	}
	if lastErr != nil {
		return last, lastErr
	}
	return last, nil
}

func pollAsyncJob(ctx context.Context, client *http.Client, cfg config, spec jobSpec, result *jobResult, accepted map[string]interface{}) error {
	jobID := stringField(accepted, "job_id")
	if jobID == "" {
		return fmt.Errorf("async job response did not include job_id")
	}
	result.JobID = jobID

	pollCtx, cancel := context.WithTimeout(ctx, spec.Poll.Timeout)
	defer cancel()
	pollPath := spec.Poll.PathPrefix + "/" + url.PathEscape(jobID)
	for {
		requestCtx, requestCancel := context.WithTimeout(pollCtx, spec.Timeout)
		response, err := doJSON(requestCtx, client, http.MethodGet, cfg.BaseURL+pollPath, nil)
		requestCancel()
		result.Polls++
		if err != nil {
			if pollCtx.Err() != nil {
				return pollCtx.Err()
			}
			return err
		}
		result.HTTPStatus = response.StatusCode
		result.Response = summarizeResponse(response.Data)
		if !successHTTP(response.StatusCode) {
			return fmt.Errorf("poll %s returned HTTP %d", pollPath, response.StatusCode)
		}
		status := strings.ToLower(stringField(response.Data, "status"))
		switch status {
		case "completed", "succeeded", "success":
			result.Passed = true
			result.Status = "passed"
			return nil
		case "failed", "error":
			if errObj := objectField(response.Data, "error"); errObj != nil {
				return fmt.Errorf("async job failed: %v", errObj)
			}
			return fmt.Errorf("async job failed")
		case "queued", "running", "accepted", "":
			if err := sleepContext(pollCtx, spec.Poll.Interval); err != nil {
				return err
			}
		default:
			return fmt.Errorf("async job returned unknown status %q", status)
		}
	}
}

func successHTTP(status int) bool {
	return status >= 200 && status < 300
}

func requestIDFromPayload(payload map[string]interface{}) string {
	if payload == nil {
		return ""
	}
	value, _ := payload["request_id"].(string)
	return strings.TrimSpace(value)
}
