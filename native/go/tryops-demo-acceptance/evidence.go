package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type evidenceSpec struct {
	Name     string
	Path     string
	Validate func(root string, path string, data map[string]interface{}) []string
}

type sourceSpec struct {
	Name     string
	Path     string
	Contains []string
}

func buildEvidenceSpecs() []evidenceSpec {
	return []evidenceSpec{
		{
			Name:     "llm_pareto_recommendation",
			Path:     "artifacts/eval/llm_pareto/pareto.json",
			Validate: validateLLMPareto,
		},
		{
			Name:     "energy_carbon_gate",
			Path:     "artifacts/eval/energy/energy_sweep.json",
			Validate: validateEnergy,
		},
		{
			Name:     "full_stack_console_and_services",
			Path:     "artifacts/eval/full_stack/full_stack_smoke.json",
			Validate: validateFullStackSmoke,
		},
		{
			Name:     "native_quota_ledger",
			Path:     "artifacts/eval/quota/native_quota_ledger_smoke.json",
			Validate: validateNativeQuotaLedger,
		},
		{
			Name:     "vton_comparison_gallery",
			Path:     "artifacts/eval/vton_comparison/comparison.json",
			Validate: validateVTONComparison,
		},
		{
			Name:     "promotion_lineage",
			Path:     "reports/generated/vton-catvton-2026-06-11-001/lineage.json",
			Validate: validateLineage,
		},
		{
			Name:     "good_candidate_promotion",
			Path:     "reports/generated/vton-catvton-2026-06-11-001/promotion_decision.json",
			Validate: validatePromotionDecision,
		},
		{
			Name:     "rollback_record",
			Path:     "artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/rollback_record.json",
			Validate: validateRollback,
		},
		{
			Name:     "governance_mapping",
			Path:     "artifacts/eval/governance/governance_report.json",
			Validate: validateGovernance,
		},
	}
}

func buildSourceSpecs() []sourceSpec {
	return []sourceSpec{
		{
			Name: "professor_demo_console_view",
			Path: "web/src/components/ProfessorDemoView.tsx",
			Contains: []string{
				"ProfessorDemoView",
				"professorDemoSteps",
				"no network",
				"no GPU",
				"seeded evidence",
			},
		},
		{
			Name: "professor_demo_seeded_data",
			Path: "web/src/professor_demo_storyboard.json",
			Contains: []string{
				"Control Plane Preflight",
				"artifacts/eval/quota/native_quota_ledger_smoke.json",
				"artifacts/eval/llm_pareto/pareto.json",
				"artifacts/eval/vton_comparison/comparison.json",
				"artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/rollback_record.json",
			},
		},
	}
}

func runEvidenceChecks(root string, specs []evidenceSpec) []evidenceResult {
	results := make([]evidenceResult, 0, len(specs))
	for _, spec := range specs {
		path := resolvePath(root, spec.Path)
		result := evidenceResult{Name: spec.Name, Path: spec.Path}
		data, err := readJSONObject(path)
		if err != nil {
			result.Error = err.Error()
			results = append(results, result)
			continue
		}
		failures := spec.Validate(root, path, data)
		if len(failures) > 0 {
			result.Error = "evidence validation failed"
			result.Details = failures
			results = append(results, result)
			continue
		}
		result.Passed = true
		result.Details = []string{"validated"}
		results = append(results, result)
	}
	return results
}

func runSourceChecks(root string, specs []sourceSpec) []evidenceResult {
	results := make([]evidenceResult, 0, len(specs))
	for _, spec := range specs {
		path := resolvePath(root, spec.Path)
		result := evidenceResult{Name: spec.Name, Path: spec.Path}
		payload, err := os.ReadFile(path)
		if err != nil {
			result.Error = err.Error()
			results = append(results, result)
			continue
		}
		body := string(payload)
		var missing []string
		for _, item := range spec.Contains {
			if !strings.Contains(body, item) {
				missing = append(missing, item)
			}
		}
		if len(missing) > 0 {
			result.Error = "source validation failed"
			result.Details = missing
			results = append(results, result)
			continue
		}
		result.Passed = true
		result.Details = []string{"validated"}
		results = append(results, result)
	}
	return results
}

func validateLLMPareto(_ string, _ string, data map[string]interface{}) []string {
	var failures []string
	failures = append(failures, requireSchema(data, "tryops.llm_pareto.v1")...)
	variants := arrayField(data, "variants")
	if len(variants) < 2 {
		failures = append(failures, "expected at least two quantization variants")
	}
	recommendation := objectField(data, "recommendation")
	recommended := stringField(recommendation, "variant")
	if recommended == "" {
		failures = append(failures, "missing recommendation.variant")
	}
	if len(arrayField(data, "pareto_frontier")) == 0 {
		failures = append(failures, "empty pareto_frontier")
	}
	if recommended != "" && !variantHasPassingSLO(variants, recommended) {
		failures = append(failures, fmt.Sprintf("recommended variant %q has no passing SLO", recommended))
	}
	return failures
}

func validateEnergy(_ string, _ string, data map[string]interface{}) []string {
	var failures []string
	failures = append(failures, requireSchema(data, "tryops.energy_report.v1")...)
	if len(arrayField(data, "variants")) == 0 {
		failures = append(failures, "missing energy variants")
	}
	gate := objectField(data, "carbon_gate")
	if !boolField(gate, "passed") {
		failures = append(failures, "carbon gate did not pass")
	}
	if stringField(gate, "verdict") != "pass" {
		failures = append(failures, "carbon gate verdict is not pass")
	}
	return failures
}

func validateFullStackSmoke(_ string, _ string, data map[string]interface{}) []string {
	var failures []string
	failures = append(failures, requireSchema(data, "tryops.full_stack_smoke.v1")...)
	if !boolField(data, "passed") {
		failures = append(failures, "full stack smoke did not pass")
	}
	checks := arrayField(data, "checks")
	required := map[string]bool{
		"gateway_console":                false,
		"gateway_spa_fallback":           false,
		"llm_generation_through_gateway": false,
		"gateway_metrics":                false,
		"minio_ready":                    false,
		"mlflow_health":                  false,
	}
	for _, item := range checks {
		check, _ := item.(map[string]interface{})
		name := stringField(check, "name")
		if _, ok := required[name]; ok {
			required[name] = boolField(check, "passed")
		}
	}
	for name, passed := range required {
		if !passed {
			failures = append(failures, fmt.Sprintf("required stack check %q did not pass", name))
		}
	}
	return failures
}

func validateNativeQuotaLedger(_ string, _ string, data map[string]interface{}) []string {
	var failures []string
	failures = append(failures, requireSchema(data, "tryops.native_quota_batch.v1")...)
	if !boolField(data, "available") {
		failures = append(failures, "native quota ledger is not available")
	}
	decisions := arrayField(data, "decisions")
	if len(decisions) == 0 {
		failures = append(failures, "missing quota decisions")
	}
	hasAllowed := false
	hasRemainingCapacity := false
	for _, item := range decisions {
		decision, _ := item.(map[string]interface{})
		if boolField(decision, "allowed") {
			hasAllowed = true
		}
		for _, checkItem := range arrayField(decision, "checks") {
			check, _ := checkItem.(map[string]interface{})
			if numberField(check, "limit") > 0 && numberField(check, "remaining_after") >= 0 {
				hasRemainingCapacity = true
			}
		}
	}
	if !hasAllowed {
		failures = append(failures, "no allowed quota decision")
	}
	if !hasRemainingCapacity {
		failures = append(failures, "quota checks do not expose remaining capacity")
	}
	if len(nestedArray(data, "snapshot", "usage")) == 0 {
		failures = append(failures, "missing quota usage snapshot")
	}
	return failures
}

func validateVTONComparison(root string, _ string, data map[string]interface{}) []string {
	var failures []string
	failures = append(failures, requireSchema(data, "tryops.vton_comparison.v1")...)
	runs := arrayField(data, "runs")
	if len(runs) < 2 {
		failures = append(failures, "expected at least two VTON comparison runs")
	}
	if stringField(data, "winner_by_structural_similarity") == "" {
		failures = append(failures, "missing structural-similarity winner")
	}
	for _, item := range runs {
		run, _ := item.(map[string]interface{})
		output := stringField(run, "output_path")
		if output == "" {
			failures = append(failures, "comparison run missing output_path")
			continue
		}
		if _, err := os.Stat(resolvePath(root, output)); err != nil {
			failures = append(failures, fmt.Sprintf("missing VTON output %s: %v", output, err))
		}
	}
	return failures
}

func validateLineage(_ string, _ string, data map[string]interface{}) []string {
	var failures []string
	failures = append(failures, requireSchema(data, "tryops.lineage.v1")...)
	if stringField(data, "candidate_id") == "" {
		failures = append(failures, "missing candidate_id")
	}
	model := objectField(data, "model")
	if !boolField(model, "signed") {
		failures = append(failures, "model is not signed")
	}
	provenance := objectField(data, "provenance")
	if !boolField(provenance, "verified") {
		failures = append(failures, "model provenance is not verified")
	}
	if stringField(provenance, "predicate_type") != "https://slsa.dev/provenance/v1" {
		failures = append(failures, "provenance predicate type is not SLSA v1")
	}
	return failures
}

func validatePromotionDecision(_ string, _ string, data map[string]interface{}) []string {
	if approved, _ := data["approved"].(bool); !approved {
		return []string{"good candidate promotion was not approved"}
	}
	if stringField(data, "target_stage") != "champion" {
		return []string{"promotion target_stage is not champion"}
	}
	return nil
}

func validateRollback(_ string, _ string, data map[string]interface{}) []string {
	var failures []string
	failures = append(failures, requireSchema(data, "tryops.rollback_record.v1")...)
	if stringField(data, "status") != "recorded" {
		failures = append(failures, "rollback status is not recorded")
	}
	if stringField(data, "restored_candidate_id") == "" {
		failures = append(failures, "missing restored_candidate_id")
	}
	if stringField(data, "rolled_back_candidate_id") == "" {
		failures = append(failures, "missing rolled_back_candidate_id")
	}
	return failures
}

func validateGovernance(_ string, _ string, data map[string]interface{}) []string {
	var failures []string
	checks := objectField(data, "mapping_checks")
	if checks == nil {
		return []string{"missing mapping_checks"}
	}
	if len(nestedArray(data, "mapping_checks", "nist", "missing_functions")) > 0 {
		failures = append(failures, "NIST mapping has missing functions")
	}
	if len(nestedArray(data, "mapping_checks", "nist", "risks_without_evidence")) > 0 {
		failures = append(failures, "NIST mapping has risks without evidence")
	}
	if len(nestedArray(data, "mapping_checks", "owasp_llm_top10_2025", "missing_ids")) > 0 {
		failures = append(failures, "OWASP mapping has missing IDs")
	}
	if len(nestedArray(data, "mapping_checks", "owasp_llm_top10_2025", "risks_without_evidence")) > 0 {
		failures = append(failures, "OWASP mapping has risks without evidence")
	}
	return failures
}

func variantHasPassingSLO(variants []interface{}, name string) bool {
	for _, item := range variants {
		variant, _ := item.(map[string]interface{})
		if stringField(variant, "variant") != name {
			continue
		}
		slo := objectField(variant, "slo")
		return stringField(slo, "verdict") == "pass"
	}
	return false
}

func displayPath(root string, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return path
	}
	return rel
}
