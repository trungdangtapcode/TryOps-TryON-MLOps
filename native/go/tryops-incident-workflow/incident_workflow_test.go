package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestEvaluateWorkflowBuildsIncidentReportAndPostmortem(t *testing.T) {
	root := t.TempDir()
	t.Setenv("GLITCHTIP_DSN", "")
	t.Setenv("TRYOPS_ERROR_TRACKING_DSN", "")
	t.Setenv("SENTRY_DSN", "")
	writeFixture(t, root, "native/go/tryops-controller/server.go", `package main
func register() {
	_ = "/alerts/webhook"
}`)
	writeFixture(t, root, "native/go/tryops-controller/promotion.go", `package main
func action() string { return "open incident review for vton" }
`)
	writeFixture(t, root, "native/go/tryops-event-dispatcher/events.go", `package main
var supported = map[string]bool{"tryops.incident.updated": true}
`)
	writeFixture(t, root, "docs/incident_postmortem_template.md", defaultPostmortemTemplate())
	writeFixture(t, root, "artifacts/deployments/rollback_state.json", `{
  "schema_version": "tryops.rollback_state.v1",
  "updated_at": "2026-06-11T00:00:00Z",
  "latest_rollback": {
    "schema_version": "tryops.rollback_record.v1",
    "package_id": "vton-catvton-2026-06-11-001-production-demo",
    "profile": "production-demo",
    "status": "completed",
    "reason": "local rollback drill",
    "rolled_back_candidate_id": "vton-catvton-2026-06-11-001",
    "restored_candidate_id": "vton-catvton-previous",
    "triggered_by": ["incident-drill"]
  }
}`)
	cfg := Config{
		RootPath:       root,
		OutputPath:     "artifacts/eval/incidents/native_incident_workflow.json",
		PostmortemPath: "artifacts/eval/incidents/postmortem_bad_candidate.md",
		TemplatePath:   "docs/incident_postmortem_template.md",
		RollbackPath:   "artifacts/deployments/rollback_state.json",
		ControllerPath: "native/go/tryops-controller",
		DispatcherPath: "native/go/tryops-event-dispatcher/events.go",
		GeneratedAt:    "2026-06-12T00:00:00Z",
	}

	report, markdown, err := evaluateWorkflow(cfg)
	if err != nil {
		t.Fatal(err)
	}

	if !report.Passed {
		payload, _ := json.MarshalIndent(report.Checks, "", "  ")
		t.Fatalf("expected report to pass, checks=%s", payload)
	}
	if report.ProductionReady {
		t.Fatalf("expected local contract to stay production_ready=false without external DSN")
	}
	if report.SchemaVersion != schemaVersion || report.ErrorTracking.LocalSchemaVersion != errorEventSchema {
		t.Fatalf("unexpected schema versions: %#v", report)
	}
	if report.Incident.Status != "resolved" || len(report.Timeline) != 5 {
		t.Fatalf("unexpected incident timeline: %#v", report.Timeline)
	}
	if report.Postmortem.ActionItems != 3 || !report.Postmortem.Written {
		t.Fatalf("unexpected postmortem summary: %#v", report.Postmortem)
	}
	if _, err := os.Stat(filepath.Join(root, cfg.PostmortemPath)); err != nil {
		t.Fatalf("postmortem was not written: %v", err)
	}
	for _, section := range requiredPostmortemSections {
		if !contains(markdown, section) {
			t.Fatalf("postmortem missing section %s", section)
		}
	}
}

func TestValidateErrorEventRejectsMissingTrace(t *testing.T) {
	event := buildErrorEvent("2026-06-12T00:00:00Z", AlertSummary{Workload: "vton", AlertNames: []string{"A"}, Severity: "page"})
	event.TraceID = "00000000000000000000000000000000"
	failures := validateErrorEvent(event)
	if len(failures) == 0 {
		t.Fatal("expected invalid trace id to fail validation")
	}
}

func writeFixture(t *testing.T, root string, path string, body string) {
	t.Helper()
	fullPath := filepath.Join(root, path)
	if err := os.MkdirAll(filepath.Dir(fullPath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(fullPath, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func contains(value string, needle string) bool {
	return len(needle) == 0 || (len(value) >= len(needle) && indexOf(value, needle) >= 0)
}

func indexOf(value string, needle string) int {
	for i := 0; i+len(needle) <= len(value); i++ {
		if value[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}
