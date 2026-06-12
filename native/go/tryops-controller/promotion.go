package main

import (
	"net/http"
	"strconv"
	"strings"
)

func evaluateRegistryWebhook(payload RegistryWebhookPayload) RegistryWebhookResponse {
	event := strings.TrimSpace(payload.Entity + "." + payload.Action)
	data := payload.Data
	actions := []string{}
	if event != "model_version_alias.created" {
		actions = append(actions, "reject: event must be model_version_alias.created")
	}
	alias := stringField(data, "alias")
	if alias != "champion" && alias != "staging" {
		actions = append(actions, "reject: model alias must be champion or staging")
	}
	candidateID := stringField(data, "candidate_id")
	if candidateID == "" {
		candidateID = stringField(nestedMap(data, "tags"), "candidate_id")
	}
	packageID := stringField(data, "package_id")
	if packageID == "" {
		packageID = stringField(nestedMap(data, "tags"), "package_id")
	}
	workload := stringField(data, "workload")
	if workload == "" {
		workload = stringField(nestedMap(data, "tags"), "workload")
	}
	if candidateID == "" {
		actions = append(actions, "reject: candidate_id is required")
	}
	if packageID == "" {
		actions = append(actions, "reject: package_id is required")
	}
	if workload != "vton" && workload != "llm" {
		actions = append(actions, "reject: workload must be vton or llm")
	}
	checks := nestedMap(data, "checks")
	requiredChecks := []string{
		"promotion_approved",
		"native_policy_matches_python",
		"openlineage_validation_passed",
		"gitops_validation_passed",
	}
	for _, check := range requiredChecks {
		if !boolField(checks, check) {
			actions = append(actions, "reject: deployment check "+check+" did not pass")
		}
	}
	var nativePolicy *NativePolicyResult
	if len(actions) == 0 {
		var nativeRejects []string
		nativePolicy, nativeRejects = evaluateNativePolicyGate(data, alias)
		actions = append(actions, nativeRejects...)
	}
	if len(actions) == 0 {
		actions = append(actions, "verify signed registry webhook")
		if nativePolicy != nil {
			actions = append(actions, "verify native C++ promotion policy for "+candidateID)
		}
		actions = append(actions, "load deployment package "+packageID)
		actions = append(actions, "trigger gitops sync for "+candidateID)
		actions = append(actions, "start argo rollout canary for "+alias)
	}
	return RegistryWebhookResponse{
		Accepted:     acceptedWebhookActions(actions),
		Event:        event,
		CandidateID:  candidateID,
		PackageID:    packageID,
		NativePolicy: nativePolicy,
		Actions:      actions,
	}
}

func evaluatePromotionPRWebhook(payload map[string]interface{}) PromotionPRResponse {
	pr := nestedMap(payload, "pull_request")
	promotion := nestedMap(payload, "tryops_promotion")
	event := "pull_request." + stringField(payload, "action")
	prNumber := intField(payload, "number")
	if prNumber == 0 {
		prNumber = intField(pr, "number")
	}
	repository := stringField(nestedMap(payload, "repository"), "full_name")
	targetStage := stringField(promotion, "target_stage")
	candidateID := stringField(promotion, "candidate_id")
	packageID := stringField(promotion, "package_id")
	workload := stringField(promotion, "workload")
	mergeCommit := stringField(pr, "merge_commit_sha")
	baseRef := stringField(nestedMap(pr, "base"), "ref")
	actions := []string{}

	if event != "pull_request.closed" {
		actions = append(actions, "reject: pull_request action must be closed")
	}
	if !boolField(pr, "merged") {
		actions = append(actions, "reject: pull request must be merged")
	}
	if prNumber == 0 {
		actions = append(actions, "reject: pull request number is required")
	}
	if baseRef != "main" && baseRef != "production" {
		actions = append(actions, "reject: base branch must be main or production")
	}
	if mergeCommit == "" {
		actions = append(actions, "reject: merge commit is required")
	}
	if repository == "" {
		actions = append(actions, "reject: repository full_name is required")
	}
	if !labelPresent(pr, "tryops/promotion") {
		actions = append(actions, "reject: tryops/promotion label is required")
	}
	if candidateID == "" {
		actions = append(actions, "reject: candidate_id is required")
	}
	if packageID == "" {
		actions = append(actions, "reject: package_id is required")
	}
	if workload != "vton" && workload != "llm" {
		actions = append(actions, "reject: workload must be vton or llm")
	}
	if targetStage != "staging" && targetStage != "champion" {
		actions = append(actions, "reject: target_stage must be staging or champion")
	}
	if intField(promotion, "approval_count") < 1 {
		actions = append(actions, "reject: at least one approval is required")
	}
	requiredChecks := []string{
		"code_owner_approved",
		"commit_signature_verified",
		"status_checks_passed",
		"promotion_approved",
		"native_policy_matches_python",
		"openlineage_validation_passed",
		"gitops_validation_passed",
		"model_provenance_verified",
		"deployment_manifest_changed",
		"gitops_manifests_changed",
	}
	for _, check := range requiredChecks {
		if !boolField(promotion, check) {
			actions = append(actions, "reject: promotion PR check "+check+" did not pass")
		}
	}
	var nativePolicy *NativePolicyResult
	if len(actions) == 0 {
		var nativeRejects []string
		nativePolicy, nativeRejects = evaluateNativePolicyGate(promotion, targetStage)
		actions = append(actions, nativeRejects...)
	}
	if len(actions) == 0 {
		actions = append(actions, "verify signed GitHub pull_request webhook")
		if nativePolicy != nil {
			actions = append(actions, "verify native C++ promotion policy for "+candidateID)
		}
		actions = append(actions, "validate promotion PR #"+strconv.Itoa(prNumber))
		actions = append(actions, "promote "+candidateID+" to "+targetStage)
		actions = append(actions, "sync registry alias for "+packageID)
	}
	return PromotionPRResponse{
		Accepted:     acceptedWebhookActions(actions),
		Event:        event,
		PullRequest:  prNumber,
		CandidateID:  candidateID,
		PackageID:    packageID,
		TargetStage:  targetStage,
		MergeCommit:  mergeCommit,
		Repository:   repository,
		NativePolicy: nativePolicy,
		Actions:      actions,
	}
}

func evaluateAlertmanagerWebhook(payload AlertmanagerWebhookPayload) AlertmanagerWebhookResponse {
	actions := []string{}
	if payload.Receiver == "" {
		actions = append(actions, "reject: receiver is required")
	}
	if payload.Status != "firing" && payload.Status != "resolved" {
		actions = append(actions, "reject: status must be firing or resolved")
	}
	if len(payload.Alerts) == 0 {
		actions = append(actions, "reject: at least one alert is required")
	}
	severity := firstLabel(payload, "severity")
	workload := firstLabel(payload, "workload")
	if severity == "" {
		actions = append(actions, "reject: severity label is required")
	}
	if workload == "" {
		actions = append(actions, "reject: workload label is required")
	}
	for index, alert := range payload.Alerts {
		if alert.Labels["alertname"] == "" {
			actions = append(actions, "reject: alert "+strconv.Itoa(index)+" missing alertname")
		}
		if alert.Labels["severity"] == "" {
			actions = append(actions, "reject: alert "+strconv.Itoa(index)+" missing severity")
		}
		if alert.Labels["workload"] == "" {
			actions = append(actions, "reject: alert "+strconv.Itoa(index)+" missing workload")
		}
		if alert.Annotations["runbook_url"] == "" {
			actions = append(actions, "reject: alert "+strconv.Itoa(index)+" missing runbook_url")
		}
	}
	if len(actions) == 0 {
		actions = append(actions, "accept Alertmanager webhook")
		actions = append(actions, "open incident review for "+workload)
		if severity == "page" {
			actions = append(actions, "page operator for "+workload)
		} else {
			actions = append(actions, "create ticket for "+workload)
		}
	}
	return AlertmanagerWebhookResponse{
		Accepted:   acceptedWebhookActions(actions),
		Receiver:   payload.Receiver,
		Status:     payload.Status,
		AlertCount: len(payload.Alerts),
		Severity:   severity,
		Workload:   workload,
		Actions:    actions,
	}
}

func firstLabel(payload AlertmanagerWebhookPayload, key string) string {
	if payload.CommonLabels != nil && payload.CommonLabels[key] != "" {
		return payload.CommonLabels[key]
	}
	if payload.GroupLabels != nil && payload.GroupLabels[key] != "" {
		return payload.GroupLabels[key]
	}
	for _, alert := range payload.Alerts {
		if alert.Labels[key] != "" {
			return alert.Labels[key]
		}
	}
	return ""
}

func acceptedWebhookActions(actions []string) bool {
	if len(actions) == 0 {
		return false
	}
	return statusForActions(actions) == http.StatusAccepted
}

func statusForActions(actions []string) int {
	for _, action := range actions {
		if len(action) >= len("reject:") && action[:len("reject:")] == "reject:" {
			return http.StatusUnprocessableEntity
		}
	}
	return http.StatusAccepted
}
