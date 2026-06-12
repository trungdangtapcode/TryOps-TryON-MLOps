package main

import (
	"time"
)

func evaluate(cfg Config) (Report, error) {
	workflow, err := readText(cfg.RootPath, cfg.WorkflowPath)
	if err != nil {
		return Report{}, err
	}
	makefile, err := readText(cfg.RootPath, cfg.MakefilePath)
	if err != nil {
		return Report{}, err
	}
	tools := discoverTools()
	missing := missingRequiredTools(tools)
	checks := append(validateWorkflow(workflow), validateMakefile(makefile)...)
	evidence, evidenceChecks := inspectEvidence(cfg.RootPath, cfg)
	checks = append(checks, evidenceChecks...)
	passed := true
	for _, check := range checks {
		if !check.Passed {
			passed = false
			break
		}
	}
	productionReady := passed && len(missing) == 0 && evidenceProductionReady(cfg.RootPath, cfg)
	coverage := "native_ci_supply_chain_contract"
	if !productionReady {
		coverage = "partial_native_ci_supply_chain_contract"
	}
	return Report{
		SchemaVersion:        "tryops.native_ci_contract.v1",
		GeneratedAt:          time.Now().UTC().Format(time.RFC3339),
		Passed:               passed,
		ProductionReady:      productionReady,
		CoverageLevel:        coverage,
		WorkflowPath:         cfg.WorkflowPath,
		MakefilePath:         cfg.MakefilePath,
		MissingRequiredTools: missing,
		Tools:                tools,
		Checks:               checks,
		Evidence:             evidence,
		Research: []ResearchRef{
			{Name: "GitHub Actions artifacts", URL: "https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts", Use: "durable CI evidence upload"},
			{Name: "GitHub Actions OIDC", URL: "https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect", Use: "keyless signing identity"},
			{Name: "Docker build GitHub Actions", URL: "https://docs.docker.com/build/ci/github-actions/", Use: "image build metadata, SBOM, and provenance"},
			{Name: "Trivy GitHub Action", URL: "https://trivy.dev/latest/docs/configuration/integrations/github-actions/", Use: "HIGH/CRITICAL image scan gate"},
			{Name: "Anchore SBOM Action", URL: "https://github.com/anchore/sbom-action", Use: "Syft-backed SPDX SBOM artifact"},
			{Name: "Cosign GitHub Actions", URL: "https://docs.sigstore.dev/cosign/signing/signing_with_containers/", Use: "keyless image signing"},
		},
		Notes: []string{
			"The workflow has production CI wiring for tests, image build, SBOM, Trivy scan, artifact upload, and Cosign keyless signing.",
			"Local production readiness remains false until required external tools and CVE/signing evidence are available in this workspace.",
		},
	}, nil
}
