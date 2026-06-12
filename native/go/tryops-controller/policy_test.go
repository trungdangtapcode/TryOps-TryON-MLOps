package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func TestNativePolicyCandidateRendersCppWireFormat(t *testing.T) {
	candidate, err := nativePolicyCandidateFromValue(policyCandidateFixture())
	if err != nil {
		t.Fatalf("parse policy candidate: %v", err)
	}

	wire := renderNativePolicyWire(candidate, "champion")
	for _, want := range []string{
		"target_stage=champion\n",
		"candidate_id=vton-catvton-2026-06-11-001\n",
		"metric.garment_fidelity=0.81\n",
		"artifact.model_provenance=s3://tryops-artifacts/provenance/vton.json\n",
		"metadata.model_provenance.statement_type=https://in-toto.io/Statement/v1\n",
		"approval=risk_owner\n",
	} {
		if !strings.Contains(wire, want) {
			t.Fatalf("wire payload missing %q in:\n%s", want, wire)
		}
	}
}

func TestNativePolicyClientAcceptsExitTwoAsPolicyRejection(t *testing.T) {
	candidate, err := nativePolicyCandidateFromValue(policyCandidateFixture())
	if err != nil {
		t.Fatalf("parse policy candidate: %v", err)
	}
	script := writePolicyStub(
		t,
		`{"approved":false,"target_stage":"champion","reasons":["metric gate failed"]}`,
		2,
	)

	result, err := (NativePolicyClient{CLIPath: script}).Evaluate(context.Background(), candidate, "champion")
	if err != nil {
		t.Fatalf("evaluate rejected policy: %v", err)
	}
	if result.Decision.Approved || result.ReturnCode != 2 {
		t.Fatalf("unexpected rejected result: %+v", result)
	}
	if got := result.Decision.Reasons[0]; got != "metric gate failed" {
		t.Fatalf("reason = %q", got)
	}
}

func TestRegistryWebhookRunsConfiguredNativePolicy(t *testing.T) {
	script := writePolicyStub(
		t,
		`{"approved":true,"target_stage":"champion","reasons":["all promotion gates passed"]}`,
		0,
	)
	t.Setenv("TRYOPS_CONTROLLER_POLICY_CLI", script)
	body := registryWebhookBody(t, policyCandidateFixture())
	req := signedWebhookRequest(body, webhookSecret())
	rec := httptest.NewRecorder()

	registryWebhook(rec, req)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("registry webhook status = %d, body=%s", rec.Code, rec.Body.String())
	}
	var got RegistryWebhookResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode registry webhook response: %v", err)
	}
	if !got.Accepted || got.NativePolicy == nil || !got.NativePolicy.Decision.Approved {
		t.Fatalf("native policy was not enforced as accepted: %+v", got)
	}
	if !containsAction(got.Actions, "verify native C++ promotion policy for vton-catvton-2026-06-11-001") {
		t.Fatalf("native policy action missing: %+v", got.Actions)
	}
}

func TestRegistryWebhookRejectsNativePolicyDenial(t *testing.T) {
	script := writePolicyStub(
		t,
		`{"approved":false,"target_stage":"champion","reasons":["missing approvals: risk_owner"]}`,
		2,
	)
	t.Setenv("TRYOPS_CONTROLLER_POLICY_CLI", script)
	body := registryWebhookBody(t, policyCandidateFixture())
	req := signedWebhookRequest(body, webhookSecret())
	rec := httptest.NewRecorder()

	registryWebhook(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("registry webhook status = %d, body=%s", rec.Code, rec.Body.String())
	}
	var got RegistryWebhookResponse
	if err := json.NewDecoder(rec.Body).Decode(&got); err != nil {
		t.Fatalf("decode registry webhook response: %v", err)
	}
	if got.Accepted || got.NativePolicy == nil || got.NativePolicy.Decision.Approved {
		t.Fatalf("native policy rejection not reflected: %+v", got)
	}
	if !containsActionPrefix(got.Actions, "reject: native C++ policy rejected candidate") {
		t.Fatalf("native policy rejection action missing: %+v", got.Actions)
	}
}

func writePolicyStub(t *testing.T, decision string, exitCode int) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "tryops-policy-stub.sh")
	body := "#!/bin/sh\ncat >/dev/null\nprintf '%s\\n' '" + decision + "'\nexit " + strconv.Itoa(exitCode) + "\n"
	if err := os.WriteFile(path, []byte(body), 0o755); err != nil {
		t.Fatalf("write policy stub: %v", err)
	}
	return path
}

func registryWebhookBody(t *testing.T, candidate map[string]interface{}) []byte {
	t.Helper()
	body, err := json.Marshal(map[string]interface{}{
		"entity":    "model_version_alias",
		"action":    "created",
		"timestamp": "2026-06-11T00:00:00Z",
		"workspace": "tryops-local",
		"data": map[string]interface{}{
			"name":             "catvton-baseline",
			"alias":            "champion",
			"version":          "0.1.0",
			"candidate_id":     "vton-catvton-2026-06-11-001",
			"package_id":       "vton-catvton-2026-06-11-001-production-demo",
			"workload":         "vton",
			"policy_candidate": candidate,
			"checks": map[string]interface{}{
				"promotion_approved":            true,
				"native_policy_matches_python":  true,
				"openlineage_validation_passed": true,
				"gitops_validation_passed":      true,
			},
		},
	})
	if err != nil {
		t.Fatalf("marshal registry webhook body: %v", err)
	}
	return body
}

func policyCandidateFixture() map[string]interface{} {
	return map[string]interface{}{
		"candidate_id":  "vton-catvton-2026-06-11-001",
		"workload":      "vton",
		"model_name":    "catvton-baseline",
		"model_version": "0.1.0",
		"metrics": map[string]interface{}{
			"garment_fidelity":      0.81,
			"identity_preservation": 0.78,
			"artifact_rate":         0.08,
			"latency_p95_ms":        9300,
		},
		"artifacts": map[string]interface{}{
			"model_card":          "s3://tryops-artifacts/model-cards/vton.md",
			"data_card":           "s3://tryops-artifacts/data-cards/vitonhd.md",
			"evaluation_report":   "s3://tryops-artifacts/reports/vton.json",
			"sbom":                "s3://tryops-artifacts/sbom/vton.spdx.json",
			"model_artifact_scan": "s3://tryops-artifacts/model-scans/vton.json",
			"model_provenance":    "s3://tryops-artifacts/provenance/vton.json",
		},
		"approvals":   []interface{}{"mlops_owner", "risk_owner"},
		"risk_status": "medium_approved",
		"vulnerabilities": map[string]interface{}{
			"critical": 0,
			"high":     0,
		},
		"signed": true,
		"metadata": map[string]interface{}{
			"model_provenance": map[string]interface{}{
				"status":          "passed",
				"statement_type":  "https://in-toto.io/Statement/v1",
				"predicate_type":  "https://slsa.dev/provenance/v1",
				"signature_mode":  "local-dsse-digest",
				"signer_identity": "tryops-local-ci",
				"verified":        true,
			},
			"model_artifacts": map[string]interface{}{
				"serialization_policy": "safetensors_only",
				"scan_status":          "passed",
				"unsafe_file_count":    0,
				"safetensors_files":    1,
				"rejected_extensions":  []interface{}{},
			},
		},
	}
}

func containsAction(actions []string, want string) bool {
	for _, action := range actions {
		if action == want {
			return true
		}
	}
	return false
}

func containsActionPrefix(actions []string, want string) bool {
	for _, action := range actions {
		if strings.HasPrefix(action, want) {
			return true
		}
	}
	return false
}
