package main

import (
	"context"
	"net/http"
	"time"
)

func retryable(status int, err error) bool {
	if err != nil {
		return true
	}
	return status == http.StatusTooManyRequests || status >= http.StatusInternalServerError
}

func retryDelay(policy retryPolicy, attempt int) time.Duration {
	base := policy.BaseDelay
	if base <= 0 {
		base = 250 * time.Millisecond
	}
	delay := base * time.Duration(attempt)
	if delay > 3*time.Second {
		return 3 * time.Second
	}
	return delay
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
