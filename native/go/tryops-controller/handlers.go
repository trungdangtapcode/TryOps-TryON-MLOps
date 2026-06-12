package main

import (
	"encoding/json"
	"io"
	"net/http"
)

func health(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}
	writeJSON(w, http.StatusOK, HealthResponse{
		Status:  "ok",
		Service: "tryops-controller",
	})
}

func reconcile(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}
	var request ReconcileRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON body"})
		return
	}

	actions := []string{}
	if request.CandidateID == "" {
		actions = append(actions, "reject: candidate_id is required")
	}
	if request.Workload != "vton" && request.Workload != "llm" {
		actions = append(actions, "reject: workload must be vton or llm")
	}
	if request.TargetStage != "staging" && request.TargetStage != "champion" {
		actions = append(actions, "reject: target_stage must be staging or champion")
	}
	if len(actions) == 0 {
		actions = append(actions, "create evaluation job")
		actions = append(actions, "watch model registry status")
		actions = append(actions, "sync deployment alias after policy approval")
	}

	writeJSON(w, statusForActions(actions), ReconcileResponse{
		Accepted: len(actions) == 3 && actions[0] == "create evaluation job",
		Actions:  actions,
	})
}

func registryWebhook(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}
	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "cannot read request body"})
		return
	}
	if err := verifyMLflowSignature(r, body, webhookSecret()); err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": err.Error()})
		return
	}
	var payload RegistryWebhookPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON body"})
		return
	}
	response := evaluateRegistryWebhook(payload)
	writeJSON(w, statusForActions(response.Actions), response)
}

func githubPRWebhook(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}
	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "cannot read request body"})
		return
	}
	if err := verifyGitHubSignature(r, body, githubWebhookSecret()); err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": err.Error()})
		return
	}
	if r.Header.Get("X-GitHub-Event") != "pull_request" {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": "event must be pull_request"})
		return
	}
	var payload map[string]interface{}
	if err := json.Unmarshal(body, &payload); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON body"})
		return
	}
	response := evaluatePromotionPRWebhook(payload)
	writeJSON(w, statusForActions(response.Actions), response)
}

func alertmanagerWebhook(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}
	var payload AlertmanagerWebhookPayload
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON body"})
		return
	}
	response := evaluateAlertmanagerWebhook(payload)
	writeJSON(w, statusForActions(response.Actions), response)
}
