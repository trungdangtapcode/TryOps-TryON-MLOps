package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestEvaluateLiveSupplyChainPasses(t *testing.T) {
	root := t.TempDir()
	writeFixture(t, root, "artifacts/eval/ci/syft/filesystem.spdx.json", `{"spdxVersion":"SPDX-2.3","name":"tryops","packages":[{"name":"a"},{"name":"b"}]}`)
	writeFixture(t, root, "artifacts/eval/ci/trivy/filesystem.json", `{"SchemaVersion":2,"Results":[{"Target":"repo","Vulnerabilities":[],"Misconfigurations":[],"Secrets":[]}]}`)
	writeFixture(t, root, "artifacts/eval/ci/cosign/tryops-local.pub", "-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----\n")
	writeFixture(t, root, "artifacts/eval/ci/cosign/sbom.spdx.json.sig", "signature\n")
	writeFixture(t, root, "artifacts/eval/ci/cosign/verify-blob.txt", "Verified OK\n")
	writeFixture(t, root, "artifacts/eval/ci/syft/version.txt", "Application: syft\nVersion: 1.45.1\n")
	writeFixture(t, root, "artifacts/eval/ci/trivy/version.txt", "Version: 0.71.0\n")
	writeFixture(t, root, "artifacts/eval/ci/cosign/version.txt", "GitVersion: v2.4.1\n")

	report := evaluate(Config{RootPath: root,
		SyftSBOMPath:      "artifacts/eval/ci/syft/filesystem.spdx.json",
		TrivyReportPath:   "artifacts/eval/ci/trivy/filesystem.json",
		CosignPublicKey:   "artifacts/eval/ci/cosign/tryops-local.pub",
		CosignSignature:   "artifacts/eval/ci/cosign/sbom.spdx.json.sig",
		CosignVerifyPath:  "artifacts/eval/ci/cosign/verify-blob.txt",
		SignedBlobPath:    "artifacts/eval/ci/syft/filesystem.spdx.json",
		SyftVersionPath:   "artifacts/eval/ci/syft/version.txt",
		TrivyVersionPath:  "artifacts/eval/ci/trivy/version.txt",
		CosignVersionPath: "artifacts/eval/ci/cosign/version.txt",
	})
	if !report.Passed || !report.ProductionReady {
		t.Fatalf("expected passing production report: %#v", report.Checks)
	}
	if report.Syft.PackageCount != 2 || report.Trivy.TotalHighCritical != 0 || !report.Cosign.Verified {
		t.Fatalf("unexpected report summary: %#v", report)
	}
}

func TestEvaluateLiveSupplyChainFailsHighCritical(t *testing.T) {
	root := t.TempDir()
	writeFixture(t, root, "artifacts/eval/ci/syft/filesystem.spdx.json", `{"spdxVersion":"SPDX-2.3","packages":[{"name":"a"}]}`)
	writeFixture(t, root, "artifacts/eval/ci/trivy/filesystem.json", `{"SchemaVersion":2,"Results":[{"Vulnerabilities":[{"Severity":"CRITICAL"}]}]}`)
	writeFixture(t, root, "artifacts/eval/ci/cosign/tryops-local.pub", "-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----\n")
	writeFixture(t, root, "artifacts/eval/ci/cosign/sbom.spdx.json.sig", "signature\n")
	writeFixture(t, root, "artifacts/eval/ci/cosign/verify-blob.txt", "Verified OK\n")
	report := evaluate(Config{RootPath: root,
		SyftSBOMPath:     "artifacts/eval/ci/syft/filesystem.spdx.json",
		TrivyReportPath:  "artifacts/eval/ci/trivy/filesystem.json",
		CosignPublicKey:  "artifacts/eval/ci/cosign/tryops-local.pub",
		CosignSignature:  "artifacts/eval/ci/cosign/sbom.spdx.json.sig",
		CosignVerifyPath: "artifacts/eval/ci/cosign/verify-blob.txt",
		SignedBlobPath:   "artifacts/eval/ci/syft/filesystem.spdx.json",
	})
	if report.Passed || report.ProductionReady {
		t.Fatalf("expected high critical findings to fail")
	}
	if report.Trivy.HighCriticalVulnerabilities != 1 {
		t.Fatalf("expected one critical vulnerability: %#v", report.Trivy)
	}
}

func writeFixture(t *testing.T, root string, path string, body string) {
	t.Helper()
	full := filepath.Join(root, path)
	if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(full, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}
