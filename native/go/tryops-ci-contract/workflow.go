package main

func validateWorkflow(workflow string) []Check {
	checks := []Check{}
	addContains := func(name string, patterns []string) {
		passed, detail := containsAll(workflow, patterns)
		checks = append(checks, Check{Name: name, Passed: passed, Detail: detail})
	}
	addContains("workflow_triggers_push_pr_dispatch", []string{"pull_request:", "push:", "workflow_dispatch:"})
	addContains("workflow_oidc_and_package_permissions", []string{"contents: read", "id-token: write", "packages: write", "security-events: write"})
	addContains("workflow_language_test_setup", []string{"actions/setup-python@v5", "actions/setup-go@v5", "actions/setup-node@v4", "python -m pip install -e \".[dev]\"", "make test", "make web-typecheck web-build", "make native-go-test", "make native-rust-test", "make native-cpp-test"})
	addContains("workflow_compose_and_native_contracts", []string{"docker compose config --quiet", "docker compose --profile tls config --quiet", "make native-container-contract-sample", "make native-dependency-lock-contract-sample", "make native-ci-contract-live", "make evaluation-index-sample"})
	addContains("workflow_artifact_uploads", []string{"actions/upload-artifact@v4", "artifacts/eval", "retention-days:"})
	addContains("workflow_image_matrix_roles", []string{"role: gateway", "role: controller", "role: guardrail", "role: benchmark", "role: cpp-tools", "role: api", "role: web-assets"})
	addContains("workflow_lowercase_ghcr_image_prefix", []string{"Normalize image prefix", "tr '[:upper:]' '[:lower:]'", "IMAGE_PREFIX=${REGISTRY}/${LOWER_REPOSITORY}", "GITHUB_ENV"})
	addContains("workflow_docker_build_metadata", []string{"docker/setup-buildx-action@v3", "docker/build-push-action@v6", "load: ${{ github.event_name == 'pull_request' }}", "sbom: ${{ github.event_name != 'pull_request' }}", "provenance: ${{ github.event_name != 'pull_request' }}"})
	addContains("workflow_syft_sbom_generation", []string{"anchore/sbom-action@v0", "format: spdx-json", "output-file: artifacts/eval/ci/sbom/"})
	addContains("workflow_trivy_high_critical_gate", []string{"aquasecurity/trivy-action@", "scanners: vuln,secret,misconfig", "severity: HIGH,CRITICAL", "limit-severities-for-sarif: true", "exit-code: \"1\""})
	addContains("workflow_cosign_keyless_signing", []string{"sigstore/cosign-installer@", "cosign sign --yes", "github.event_name != 'pull_request'"})
	return checks
}
