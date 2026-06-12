package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"
)

func TestHealth(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	health(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("health status = %d, want %d", rec.Code, http.StatusOK)
	}
	var got HealthResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode health response: %v", err)
	}
	if got.Status != "ok" || got.Service != "tryops-controller" {
		t.Fatalf("unexpected health response: %+v", got)
	}
}

func TestHealthRejectsWrongMethod(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/health", nil)
	rec := httptest.NewRecorder()

	health(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("health wrong-method status = %d, want %d", rec.Code, http.StatusMethodNotAllowed)
	}
}

func TestReconcileAcceptsValidPromotion(t *testing.T) {
	body := []byte(`{"candidate_id":"c1","workload":"vton","target_stage":"champion"}`)
	req := httptest.NewRequest(http.MethodPost, "/reconcile", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	reconcile(rec, req)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("reconcile status = %d, want %d", rec.Code, http.StatusAccepted)
	}
	var got ReconcileResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode reconcile response: %v", err)
	}
	if !got.Accepted || len(got.Actions) != 3 {
		t.Fatalf("unexpected accepted response: %+v", got)
	}
}

func TestReconcileRejectsInvalidPromotion(t *testing.T) {
	body := []byte(`{"candidate_id":"","workload":"x","target_stage":"p"}`)
	req := httptest.NewRequest(http.MethodPost, "/reconcile", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	reconcile(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("reconcile invalid status = %d, want %d", rec.Code, http.StatusUnprocessableEntity)
	}
	var got ReconcileResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode invalid reconcile response: %v", err)
	}
	if got.Accepted || len(got.Actions) != 3 {
		t.Fatalf("unexpected rejected response: %+v", got)
	}
}

func TestRegistryWebhookAcceptsSignedDeploymentTrigger(t *testing.T) {
	body := []byte(`{"entity":"model_version_alias","action":"created","timestamp":"2026-06-11T00:00:00Z","workspace":"tryops-local","data":{"name":"catvton-baseline","alias":"champion","version":"0.1.0","candidate_id":"candidate-1","package_id":"package-1","workload":"vton","checks":{"promotion_approved":true,"native_policy_matches_python":true,"openlineage_validation_passed":true,"gitops_validation_passed":true}}}`)
	req := signedWebhookRequest(body, webhookSecret())
	rec := httptest.NewRecorder()

	registryWebhook(rec, req)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("registry webhook status = %d, want %d; body=%s", rec.Code, http.StatusAccepted, rec.Body.String())
	}
	var got RegistryWebhookResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode registry webhook response: %v", err)
	}
	if !got.Accepted || got.Event != "model_version_alias.created" || got.CandidateID != "candidate-1" {
		t.Fatalf("unexpected registry webhook response: %+v", got)
	}
	if len(got.Actions) != 4 || got.Actions[2] != "trigger gitops sync for candidate-1" {
		t.Fatalf("unexpected registry webhook actions: %+v", got.Actions)
	}
}

func TestRegistryWebhookRejectsInvalidSignature(t *testing.T) {
	body := []byte(`{"entity":"model_version_alias","action":"created","data":{}}`)
	req := signedWebhookRequest(body, "wrong-secret")
	rec := httptest.NewRecorder()

	registryWebhook(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("invalid signature status = %d, want %d", rec.Code, http.StatusUnauthorized)
	}
}

func TestRegistryWebhookRejectsFailedDeploymentChecks(t *testing.T) {
	body := []byte(`{"entity":"model_version_alias","action":"created","timestamp":"2026-06-11T00:00:00Z","workspace":"tryops-local","data":{"name":"catvton-baseline","alias":"champion","version":"0.1.0","candidate_id":"candidate-1","package_id":"package-1","workload":"vton","checks":{"promotion_approved":true,"native_policy_matches_python":true,"openlineage_validation_passed":true,"gitops_validation_passed":false}}}`)
	req := signedWebhookRequest(body, webhookSecret())
	rec := httptest.NewRecorder()

	registryWebhook(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("failed-check status = %d, want %d; body=%s", rec.Code, http.StatusUnprocessableEntity, rec.Body.String())
	}
	var got RegistryWebhookResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode failed-check response: %v", err)
	}
	if got.Accepted {
		t.Fatalf("failed-check webhook was accepted: %+v", got)
	}
}

func TestGitHubPRWebhookAcceptsSignedPromotion(t *testing.T) {
	body := []byte(`{"action":"closed","number":42,"repository":{"full_name":"tryops/platform"},"pull_request":{"number":42,"merged":true,"merge_commit_sha":"abc123","base":{"ref":"main"},"head":{"sha":"def456"},"labels":[{"name":"tryops/promotion"},{"name":"release/production-demo"}]},"tryops_promotion":{"candidate_id":"candidate-1","package_id":"package-1","workload":"vton","target_stage":"champion","approval_count":2,"code_owner_approved":true,"commit_signature_verified":true,"status_checks_passed":true,"promotion_approved":true,"native_policy_matches_python":true,"openlineage_validation_passed":true,"gitops_validation_passed":true,"model_provenance_verified":true,"deployment_manifest_changed":true,"gitops_manifests_changed":true}}`)
	req := signedGitHubWebhookRequest(body, githubWebhookSecret())
	rec := httptest.NewRecorder()

	githubPRWebhook(rec, req)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("github PR webhook status = %d, want %d; body=%s", rec.Code, http.StatusAccepted, rec.Body.String())
	}
	var got PromotionPRResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode github PR response: %v", err)
	}
	if !got.Accepted || got.Event != "pull_request.closed" || got.PullRequest != 42 {
		t.Fatalf("unexpected github PR response: %+v", got)
	}
	if len(got.Actions) != 4 || got.Actions[2] != "promote candidate-1 to champion" {
		t.Fatalf("unexpected github PR actions: %+v", got.Actions)
	}
}

func TestGitHubPRWebhookRejectsInvalidSignature(t *testing.T) {
	body := []byte(`{"action":"closed","number":42,"pull_request":{"merged":true}}`)
	req := signedGitHubWebhookRequest(body, "wrong-secret")
	rec := httptest.NewRecorder()

	githubPRWebhook(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("github invalid signature status = %d, want %d", rec.Code, http.StatusUnauthorized)
	}
}

func TestGitHubPRWebhookRejectsUnmergedPromotion(t *testing.T) {
	body := []byte(`{"action":"closed","number":42,"repository":{"full_name":"tryops/platform"},"pull_request":{"number":42,"merged":false,"merge_commit_sha":"abc123","base":{"ref":"main"},"labels":[{"name":"tryops/promotion"}]},"tryops_promotion":{"candidate_id":"candidate-1","package_id":"package-1","workload":"vton","target_stage":"champion","approval_count":2,"code_owner_approved":true,"commit_signature_verified":true,"status_checks_passed":true,"promotion_approved":true,"native_policy_matches_python":true,"openlineage_validation_passed":true,"gitops_validation_passed":true,"model_provenance_verified":true,"deployment_manifest_changed":true,"gitops_manifests_changed":true}}`)
	req := signedGitHubWebhookRequest(body, githubWebhookSecret())
	rec := httptest.NewRecorder()

	githubPRWebhook(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("unmerged github PR status = %d, want %d; body=%s", rec.Code, http.StatusUnprocessableEntity, rec.Body.String())
	}
	var got PromotionPRResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode unmerged github PR response: %v", err)
	}
	if got.Accepted {
		t.Fatalf("unmerged github PR was accepted: %+v", got)
	}
}

func TestAlertmanagerWebhookAcceptsPageAlert(t *testing.T) {
	body := []byte(`{"receiver":"tryops-page-webhook","status":"firing","groupLabels":{"severity":"page","workload":"llm"},"commonLabels":{"severity":"page","workload":"llm"},"alerts":[{"status":"firing","labels":{"alertname":"TryOpsLLMQualityRegression","severity":"page","workload":"llm"},"annotations":{"summary":"quality regression","runbook_url":"docs/observability_contract.md"},"startsAt":"2026-06-12T00:00:00Z"}]}`)
	req := httptest.NewRequest(http.MethodPost, "/alerts/webhook", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	alertmanagerWebhook(rec, req)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("alertmanager webhook status = %d, want %d; body=%s", rec.Code, http.StatusAccepted, rec.Body.String())
	}
	var got AlertmanagerWebhookResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode alertmanager webhook response: %v", err)
	}
	if !got.Accepted || got.Severity != "page" || got.Workload != "llm" || got.AlertCount != 1 {
		t.Fatalf("unexpected alertmanager response: %+v", got)
	}
	if len(got.Actions) != 3 || got.Actions[2] != "page operator for llm" {
		t.Fatalf("unexpected alert actions: %+v", got.Actions)
	}
}

func TestAlertmanagerWebhookRejectsMissingRunbook(t *testing.T) {
	body := []byte(`{"receiver":"tryops-page-webhook","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"TryOpsLLMQualityRegression","severity":"page","workload":"llm"},"annotations":{"summary":"quality regression"},"startsAt":"2026-06-12T00:00:00Z"}]}`)
	req := httptest.NewRequest(http.MethodPost, "/alerts/webhook", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	alertmanagerWebhook(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("missing-runbook alert status = %d, want %d", rec.Code, http.StatusUnprocessableEntity)
	}
	var got AlertmanagerWebhookResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode alertmanager reject response: %v", err)
	}
	if got.Accepted {
		t.Fatalf("missing-runbook alert was accepted: %+v", got)
	}
}

func signedWebhookRequest(body []byte, secret string) *http.Request {
	req := httptest.NewRequest(http.MethodPost, "/registry/webhook", bytes.NewReader(body))
	deliveryID := "delivery-test-001"
	timestamp := strconv.FormatInt(time.Now().UTC().Unix(), 10)
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(deliveryID + "." + timestamp + "." + string(body)))
	req.Header.Set("X-MLflow-Signature", "v1,"+base64.StdEncoding.EncodeToString(mac.Sum(nil)))
	req.Header.Set("X-MLflow-Delivery-ID", deliveryID)
	req.Header.Set("X-MLflow-Timestamp", timestamp)
	return req
}

func signedGitHubWebhookRequest(body []byte, secret string) *http.Request {
	req := httptest.NewRequest(http.MethodPost, "/github/pr-webhook", bytes.NewReader(body))
	deliveryID := "github-delivery-test-001"
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write(body)
	req.Header.Set("X-Hub-Signature-256", "sha256="+hex.EncodeToString(mac.Sum(nil)))
	req.Header.Set("X-GitHub-Delivery", deliveryID)
	req.Header.Set("X-GitHub-Event", "pull_request")
	return req
}
