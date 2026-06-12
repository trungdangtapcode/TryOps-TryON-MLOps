package main

import (
	"fmt"
	"strings"
	"time"
)

func evaluate(cfg Config) Report {
	checks := []Check{}
	syft := summarizeSyft(cfg, &checks)
	trivy := summarizeTrivy(cfg, &checks)
	cosign := summarizeCosign(cfg, &checks)

	tools := []ToolEvidence{
		{Name: "syft", Image: cfg.SyftImage, VersionOutputPath: cfg.SyftVersionPath, Version: firstVersionLine(readText(cfg.RootPath, cfg.SyftVersionPath)), Executed: syft.PackageCount > 0},
		{Name: "trivy", Image: cfg.TrivyImage, VersionOutputPath: cfg.TrivyVersionPath, Version: firstVersionLine(readText(cfg.RootPath, cfg.TrivyVersionPath)), Executed: trivy.SchemaVersion > 0},
		{Name: "cosign", Image: cfg.CosignImage, VersionOutputPath: cfg.CosignVersionPath, Version: firstVersionLine(readText(cfg.RootPath, cfg.CosignVersionPath)), Executed: cosign.Verified},
	}
	for _, tool := range tools {
		checks = append(checks, Check{
			Name:   "tool." + tool.Name + ".executed",
			Passed: tool.Executed,
			Detail: fmt.Sprintf("image=%s version=%s", tool.Image, tool.Version),
		})
	}

	passed := true
	for _, check := range checks {
		if !check.Passed {
			passed = false
			break
		}
	}
	return Report{
		SchemaVersion:   schemaVersion,
		GeneratedAt:     time.Now().UTC().Format(time.RFC3339),
		Passed:          passed,
		ProductionReady: passed,
		CoverageLevel:   "native_live_syft_trivy_cosign",
		Tools:           tools,
		Syft:            syft,
		Trivy:           trivy,
		Cosign:          cosign,
		Checks:          checks,
		Research: []ResearchRef{
			{Name: "Syft CLI", URL: "https://oss.anchore.com/docs/reference/syft/cli/", Use: "SPDX SBOM generation for filesystem source"},
			{Name: "Trivy filesystem scanning", URL: "https://trivy.dev/docs/latest/configuration/reporting/", Use: "HIGH/CRITICAL vulnerability, secret, and misconfiguration gate"},
			{Name: "Cosign blob signing", URL: "https://docs.sigstore.dev/cosign/signing/signing_with_blobs/", Use: "local SBOM signature and verification evidence"},
		},
		Notes: []string{
			"Syft, Trivy, and Cosign are executed from pinned open-source container images so host PATH installation is not required.",
			"Cosign uses a temporary local key for blob-signature proof; GitHub Actions keeps the keyless OCI image signing contract.",
			"Trivy is run with HIGH/CRITICAL severity and scanners=vuln,secret,misconfig; any finding fails production readiness.",
		},
	}
}

func summarizeSyft(cfg Config, checks *[]Check) SyftSummary {
	data, err := readJSON(cfg.RootPath, cfg.SyftSBOMPath)
	if err != nil {
		*checks = append(*checks, Check{Name: "syft.sbom.present", Passed: false, Detail: err.Error()})
		return SyftSummary{Path: cfg.SyftSBOMPath}
	}
	spdx := stringField(data, "spdxVersion")
	packages := arrayField(data, "packages")
	documentName := stringField(data, "name")
	*checks = append(*checks,
		Check{Name: "syft.sbom.spdx_schema", Passed: strings.HasPrefix(spdx, "SPDX-"), Detail: spdx},
		Check{Name: "syft.sbom.packages_present", Passed: len(packages) > 0, Detail: fmt.Sprintf("packages=%d", len(packages))},
	)
	return SyftSummary{Path: cfg.SyftSBOMPath, SPDX: spdx, PackageCount: len(packages), DocumentName: documentName}
}

func summarizeTrivy(cfg Config, checks *[]Check) TrivySummary {
	summary := TrivySummary{Path: cfg.TrivyReportPath, BySeverity: map[string]int{}}
	data, err := readJSON(cfg.RootPath, cfg.TrivyReportPath)
	if err != nil {
		*checks = append(*checks, Check{Name: "trivy.report.present", Passed: false, Detail: err.Error()})
		return summary
	}
	summary.SchemaVersion = intField(data, "SchemaVersion")
	results := arrayField(data, "Results")
	summary.Results = len(results)
	for _, item := range results {
		result, _ := item.(map[string]interface{})
		for _, vuln := range arrayField(result, "Vulnerabilities") {
			severity := severityOf(vuln)
			summary.BySeverity[severity]++
			if highCritical(severity) {
				summary.HighCriticalVulnerabilities++
			}
		}
		for _, misconfig := range arrayField(result, "Misconfigurations") {
			severity := severityOf(misconfig)
			summary.BySeverity[severity]++
			if highCritical(severity) {
				summary.HighCriticalMisconfigurations++
			}
		}
		for _, secret := range arrayField(result, "Secrets") {
			severity := severityOf(secret)
			summary.BySeverity[severity]++
			if highCritical(severity) {
				summary.HighCriticalSecrets++
			}
		}
	}
	summary.TotalHighCritical = summary.HighCriticalVulnerabilities + summary.HighCriticalMisconfigurations + summary.HighCriticalSecrets
	*checks = append(*checks,
		Check{Name: "trivy.report.schema", Passed: summary.SchemaVersion > 0, Detail: fmt.Sprintf("schema=%d", summary.SchemaVersion)},
		Check{Name: "trivy.high_critical.vulnerabilities", Passed: summary.HighCriticalVulnerabilities == 0, Detail: fmt.Sprintf("%d", summary.HighCriticalVulnerabilities)},
		Check{Name: "trivy.high_critical.misconfigurations", Passed: summary.HighCriticalMisconfigurations == 0, Detail: fmt.Sprintf("%d", summary.HighCriticalMisconfigurations)},
		Check{Name: "trivy.high_critical.secrets", Passed: summary.HighCriticalSecrets == 0, Detail: fmt.Sprintf("%d", summary.HighCriticalSecrets)},
	)
	return summary
}

func summarizeCosign(cfg Config, checks *[]Check) CosignSummary {
	verifyOutput := readText(cfg.RootPath, cfg.CosignVerifyPath)
	publicKey := readText(cfg.RootPath, cfg.CosignPublicKey)
	signatureBytes := fileSize(cfg.RootPath, cfg.CosignSignature)
	publicKeyBytes := fileSize(cfg.RootPath, cfg.CosignPublicKey)
	signedBlobBytes := fileSize(cfg.RootPath, cfg.SignedBlobPath)
	summary := CosignSummary{
		SignedBlobPath:   cfg.SignedBlobPath,
		PublicKeyPath:    cfg.CosignPublicKey,
		SignaturePath:    cfg.CosignSignature,
		VerifyOutputPath: cfg.CosignVerifyPath,
		PublicKeyBytes:   publicKeyBytes,
		SignatureBytes:   signatureBytes,
		Verified:         strings.Contains(verifyOutput, "Verified OK"),
		TLogSkipped:      strings.Contains(strings.ToLower(verifyOutput), "tlog"),
	}
	*checks = append(*checks,
		Check{Name: "cosign.signed_blob.present", Passed: signedBlobBytes > 0, Detail: fmt.Sprintf("bytes=%d", signedBlobBytes)},
		Check{Name: "cosign.public_key.present", Passed: publicKeyBytes > 0 && strings.Contains(publicKey, "BEGIN PUBLIC KEY"), Detail: fmt.Sprintf("bytes=%d", publicKeyBytes)},
		Check{Name: "cosign.signature.present", Passed: signatureBytes > 0, Detail: fmt.Sprintf("bytes=%d", signatureBytes)},
		Check{Name: "cosign.verify_blob.ok", Passed: summary.Verified, Detail: strings.TrimSpace(verifyOutput)},
	)
	return summary
}

func severityOf(item interface{}) string {
	data, _ := item.(map[string]interface{})
	return strings.ToUpper(stringField(data, "Severity"))
}

func highCritical(severity string) bool {
	return severity == "HIGH" || severity == "CRITICAL"
}
