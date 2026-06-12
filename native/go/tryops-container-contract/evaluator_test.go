package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestEvaluatePassesRepositoryContainerSplit(t *testing.T) {
	root := repoRoot(t)
	manifest, err := loadManifest(root, "configs/container_images.json")
	if err != nil {
		t.Fatal(err)
	}
	compose, err := loadCompose(root, "docker-compose.yml")
	if err != nil {
		t.Fatal(err)
	}

	report := evaluate(root, manifest, compose, "configs/container_images.json", "docker-compose.yml")
	if !report.Passed {
		t.Fatalf("expected container contract to pass; failed checks: %#v", failedChecks(report.Checks))
	}
	if report.Summary.RequiredRoles != 7 || report.Summary.ComposeRoles != 7 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func TestEvaluateRejectsMissingRole(t *testing.T) {
	report := evaluate(".", Manifest{
		SchemaVersion: "tryops.container_images.v1",
		Images:        []ImageSpec{{Role: "api", Dockerfile: "Dockerfile.api", ComposeService: "api"}},
	}, ComposeFile{Services: map[string]ComposeService{}}, "manifest", "compose")
	if report.Passed {
		t.Fatalf("expected missing roles to fail")
	}
}

func failedChecks(checks []Check) []Check {
	failed := []Check{}
	for _, check := range checks {
		if !check.Passed {
			failed = append(failed, check)
		}
	}
	return failed
}

func repoRoot(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	for {
		if _, err := os.Stat(filepath.Join(wd, "MLOPS_VTON_LLM_ENTERPRISE_ROADMAP.md")); err == nil {
			return wd
		}
		next := filepath.Dir(wd)
		if next == wd {
			t.Fatal("repository root not found")
		}
		wd = next
	}
}
