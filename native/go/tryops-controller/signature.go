package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"net/http"
	"strconv"
	"strings"
	"time"
)

func verifyMLflowSignature(r *http.Request, body []byte, secret string) error {
	signature := r.Header.Get("X-MLflow-Signature")
	deliveryID := r.Header.Get("X-MLflow-Delivery-ID")
	timestamp := r.Header.Get("X-MLflow-Timestamp")
	if signature == "" {
		return errString("missing X-MLflow-Signature header")
	}
	if deliveryID == "" {
		return errString("missing X-MLflow-Delivery-ID header")
	}
	if timestamp == "" {
		return errString("missing X-MLflow-Timestamp header")
	}
	if !freshTimestamp(timestamp, 5*time.Minute) {
		return errString("webhook timestamp is outside the allowed freshness window")
	}
	if !strings.HasPrefix(signature, "v1,") {
		return errString("unsupported signature version")
	}
	content := deliveryID + "." + timestamp + "." + string(body)
	mac := hmac.New(sha256.New, []byte(secret))
	if _, err := mac.Write([]byte(content)); err != nil {
		return err
	}
	expected := "v1," + base64.StdEncoding.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(signature), []byte(expected)) {
		return errString("invalid webhook signature")
	}
	return nil
}

func verifyGitHubSignature(r *http.Request, body []byte, secret string) error {
	signature := r.Header.Get("X-Hub-Signature-256")
	deliveryID := r.Header.Get("X-GitHub-Delivery")
	if signature == "" {
		return errString("missing X-Hub-Signature-256 header")
	}
	if deliveryID == "" {
		return errString("missing X-GitHub-Delivery header")
	}
	if !strings.HasPrefix(signature, "sha256=") {
		return errString("unsupported GitHub signature version")
	}
	mac := hmac.New(sha256.New, []byte(secret))
	if _, err := mac.Write(body); err != nil {
		return err
	}
	expected := "sha256=" + hex.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(signature), []byte(expected)) {
		return errString("invalid GitHub webhook signature")
	}
	return nil
}

func freshTimestamp(value string, maxAge time.Duration) bool {
	seconds, err := strconv.ParseInt(value, 10, 64)
	if err != nil {
		return false
	}
	eventTime := time.Unix(seconds, 0)
	age := time.Since(eventTime)
	return age >= 0 && age <= maxAge
}

type errString string

func (e errString) Error() string {
	return string(e)
}

func webhookSecret() string {
	return getenv("TRYOPS_WEBHOOK_SECRET", "tryops-local-webhook")
}

func githubWebhookSecret() string {
	return getenv("TRYOPS_GITHUB_WEBHOOK_SECRET", "tryops-local-github-webhook")
}
