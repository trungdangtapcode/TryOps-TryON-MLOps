package main

import "fmt"

func inspectEvidence(root string, cfg Config) ([]EvidenceRef, []Check) {
	var evidence []EvidenceRef
	var checks []Check
	addJSON := func(name, path, expectedSchema string, required bool) {
		data, err := readJSON(root, path)
		if err != nil {
			status := "missing"
			detail := err.Error()
			evidence = append(evidence, EvidenceRef{Name: name, Path: path, Status: status, Detail: detail})
			checks = append(checks, Check{Name: name + "_artifact_present", Passed: !required, Detail: detail})
			return
		}
		schema := stringField(data, "schema_version")
		passed := schema == expectedSchema
		detail := fmt.Sprintf("schema=%s", schema)
		status := "present"
		if ok, okSet := boolField(data, "passed"); okSet {
			if ok {
				status = "passed"
			} else {
				status = "failed"
			}
			detail = fmt.Sprintf("%s passed=%t", detail, ok)
		}
		if prod, okSet := boolField(data, "production_ready"); okSet {
			detail = fmt.Sprintf("%s production_ready=%t", detail, prod)
		}
		evidence = append(evidence, EvidenceRef{Name: name, Path: path, SchemaVersion: schema, Status: status, Detail: detail})
		checks = append(checks, Check{Name: name + "_schema", Passed: passed, Detail: detail})
	}
	addJSON("vulnerability_scan", cfg.VulnerabilityPath, "tryops.vulnerability_scan.v1", true)
	addJSON("supply_chain", cfg.SupplyChainPath, "tryops.supply_chain_report.v1", true)
	addJSON("container_contract", cfg.ContainerReportPath, "tryops.native_container_contract.v1", true)
	return evidence, checks
}

func evidenceProductionReady(root string, cfg Config) bool {
	vuln, err := readJSON(root, cfg.VulnerabilityPath)
	if err != nil {
		return false
	}
	if prod, ok := boolField(vuln, "production_ready"); ok && !prod {
		return false
	}
	supply, err := readJSON(root, cfg.SupplyChainPath)
	if err != nil {
		return false
	}
	if passed, ok := boolField(supply, "passed"); !ok || !passed {
		return false
	}
	container, err := readJSON(root, cfg.ContainerReportPath)
	if err != nil {
		return false
	}
	if passed, ok := boolField(container, "passed"); !ok || !passed {
		return false
	}
	return true
}
