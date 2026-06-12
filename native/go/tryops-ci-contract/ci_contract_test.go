package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestValidateWorkflowRequiresSupplyChainGates(t *testing.T) {
	workflow := `
pull_request:
push:
workflow_dispatch:
contents: read
id-token: write
packages: write
security-events: write
actions/setup-python@v5
actions/setup-go@v5
actions/setup-node@v4
make test
make web-typecheck web-build
make native-go-test
make native-live-supply-chain-test
make native-rust-test
make native-cpp-test
docker compose config --quiet
docker compose --profile tls config --quiet
make native-container-contract-sample
make native-dependency-lock-contract-sample
make native-ci-contract-live
make evaluation-index-sample
actions/upload-artifact@v4
artifacts/eval
retention-days:
role: gateway
role: controller
role: guardrail
role: benchmark
role: cpp-tools
role: api
role: web-assets
docker/setup-buildx-action@v3
docker/build-push-action@v6
sbom: true
provenance: true
anchore/sbom-action@v0
format: spdx-json
output-file: artifacts/eval/ci/sbom/
aquasecurity/trivy-action@
scanners: vuln,secret,misconfig
severity: HIGH,CRITICAL
exit-code: "1"
sigstore/cosign-installer@
cosign sign --yes
github.event_name != 'pull_request'
`
	checks := validateWorkflow(workflow)
	for _, check := range checks {
		if !check.Passed {
			t.Fatalf("%s failed: %s", check.Name, check.Detail)
		}
	}
}

func TestEvaluatePartialWhenToolsMissingButContractValid(t *testing.T) {
	root := t.TempDir()
	writeFile(t, root, ".github/workflows/ci.yml", `
pull_request:
push:
workflow_dispatch:
contents: read
id-token: write
packages: write
security-events: write
actions/setup-python@v5
actions/setup-go@v5
actions/setup-node@v4
make test
make web-typecheck web-build
make native-go-test
make native-live-supply-chain-test
make native-rust-test
make native-cpp-test
docker compose config --quiet
docker compose --profile tls config --quiet
make native-container-contract-sample
make native-dependency-lock-contract-sample
make native-ci-contract-live
make evaluation-index-sample
actions/upload-artifact@v4
artifacts/eval
retention-days:
role: gateway
role: controller
role: guardrail
role: benchmark
role: cpp-tools
role: api
role: web-assets
docker/setup-buildx-action@v3
docker/build-push-action@v6
sbom: true
provenance: true
anchore/sbom-action@v0
format: spdx-json
output-file: artifacts/eval/ci/sbom/
aquasecurity/trivy-action@
scanners: vuln,secret,misconfig
severity: HIGH,CRITICAL
exit-code: "1"
sigstore/cosign-installer@
cosign sign --yes
github.event_name != 'pull_request'
`)
	writeFile(t, root, "Makefile", `
ci: test web-typecheck native-go-test native-rust-test native-cpp-test supply-chain-sample vulnerability-scan-sample native-live-supply-chain-sample native-container-contract-sample native-dependency-lock-contract-sample native-ci-contract-live evaluation-index-sample
native-live-supply-chain-build:
native-live-supply-chain-test:
native-live-supply-chain-sample:
native-ci-contract-build:
native-ci-contract-test:
native-ci-contract-sample:
native-ci-contract-live:
`)
	writeFile(t, root, "artifacts/eval/security/vulnerability_scan_report.json", `{"schema_version":"tryops.vulnerability_scan.v1","passed":true,"production_ready":false}`)
	writeFile(t, root, "artifacts/eval/supply_chain/supply_chain_report.json", `{"schema_version":"tryops.supply_chain_report.v1","passed":true}`)
	writeFile(t, root, "artifacts/eval/containers/native_container_contract_report.json", `{"schema_version":"tryops.native_container_contract.v1","passed":true}`)
	report, err := evaluate(Config{
		RootPath:            root,
		WorkflowPath:        ".github/workflows/ci.yml",
		MakefilePath:        "Makefile",
		VulnerabilityPath:   "artifacts/eval/security/vulnerability_scan_report.json",
		SupplyChainPath:     "artifacts/eval/supply_chain/supply_chain_report.json",
		LiveSupplyChainPath: "artifacts/eval/ci/live_supply_chain_report.json",
		ContainerReportPath: "artifacts/eval/containers/native_container_contract_report.json",
	})
	if err != nil {
		t.Fatal(err)
	}
	if !report.Passed {
		t.Fatalf("expected contract pass")
	}
	if report.ProductionReady {
		t.Fatalf("expected partial production readiness")
	}
	if report.CoverageLevel != "partial_native_ci_supply_chain_contract" {
		t.Fatalf("unexpected coverage: %s", report.CoverageLevel)
	}
}

func TestEvaluateProductionReadyWithLiveSupplyChainEvidence(t *testing.T) {
	root := t.TempDir()
	writeFile(t, root, ".github/workflows/ci.yml", `
pull_request:
push:
workflow_dispatch:
contents: read
id-token: write
packages: write
security-events: write
actions/setup-python@v5
actions/setup-go@v5
actions/setup-node@v4
make test
make web-typecheck web-build
make native-go-test
make native-live-supply-chain-test
make native-rust-test
make native-cpp-test
docker compose config --quiet
docker compose --profile tls config --quiet
make native-container-contract-sample
make native-dependency-lock-contract-sample
make native-ci-contract-live
make evaluation-index-sample
actions/upload-artifact@v4
artifacts/eval
retention-days:
role: gateway
role: controller
role: guardrail
role: benchmark
role: cpp-tools
role: api
role: web-assets
docker/setup-buildx-action@v3
docker/build-push-action@v6
sbom: true
provenance: true
anchore/sbom-action@v0
format: spdx-json
output-file: artifacts/eval/ci/sbom/
aquasecurity/trivy-action@
scanners: vuln,secret,misconfig
severity: HIGH,CRITICAL
exit-code: "1"
sigstore/cosign-installer@
cosign sign --yes
github.event_name != 'pull_request'
`)
	writeFile(t, root, "Makefile", `
ci: test web-typecheck native-go-test native-rust-test native-cpp-test supply-chain-sample vulnerability-scan-sample native-live-supply-chain-sample native-container-contract-sample native-dependency-lock-contract-sample native-ci-contract-live evaluation-index-sample
native-live-supply-chain-build:
native-live-supply-chain-test:
native-live-supply-chain-sample:
native-ci-contract-build:
native-ci-contract-test:
native-ci-contract-sample:
native-ci-contract-live:
`)
	writeFile(t, root, "artifacts/eval/security/vulnerability_scan_report.json", `{"schema_version":"tryops.vulnerability_scan.v1","passed":true,"production_ready":false}`)
	writeFile(t, root, "artifacts/eval/supply_chain/supply_chain_report.json", `{"schema_version":"tryops.supply_chain_report.v1","passed":true}`)
	writeFile(t, root, "artifacts/eval/ci/live_supply_chain_report.json", `{"schema_version":"tryops.live_supply_chain.v1","passed":true,"production_ready":true}`)
	writeFile(t, root, "artifacts/eval/containers/native_container_contract_report.json", `{"schema_version":"tryops.native_container_contract.v1","passed":true}`)
	report, err := evaluateWithTools(Config{
		RootPath:            root,
		WorkflowPath:        ".github/workflows/ci.yml",
		MakefilePath:        "Makefile",
		VulnerabilityPath:   "artifacts/eval/security/vulnerability_scan_report.json",
		SupplyChainPath:     "artifacts/eval/supply_chain/supply_chain_report.json",
		LiveSupplyChainPath: "artifacts/eval/ci/live_supply_chain_report.json",
		ContainerReportPath: "artifacts/eval/containers/native_container_contract_report.json",
	}, []ToolStatus{
		{Name: "docker", Required: true, Available: true, Path: "/usr/bin/docker"},
		{Name: "syft", Required: true},
		{Name: "trivy", Required: true},
		{Name: "cosign", Required: true},
	})
	if err != nil {
		t.Fatal(err)
	}
	if !report.Passed || !report.ProductionReady {
		t.Fatalf("expected production-ready live contract: %#v", report)
	}
	if len(report.MissingRequiredTools) != 0 {
		t.Fatalf("expected live evidence to cover host scanner tools, got %#v", report.MissingRequiredTools)
	}
	if report.CoverageLevel != "native_ci_supply_chain_contract" {
		t.Fatalf("unexpected coverage: %s", report.CoverageLevel)
	}
}

func writeFile(t *testing.T, root, rel, content string) {
	t.Helper()
	path := filepath.Join(root, rel)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}
