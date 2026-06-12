package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestStatusForReportUsesPartialCoverage(t *testing.T) {
	status := statusForReport("artifacts/eval/security/vulnerability_scan_report.json", map[string]interface{}{
		"schema_version":     "tryops.vulnerability_scan.v1",
		"passed":             true,
		"coverage_level":     "partial",
		"production_ready":   false,
		"missing_tool_count": float64(7),
	})
	if status != "partial" {
		t.Fatalf("expected partial status, got %q", status)
	}
}

func TestSummaryLLMPareto(t *testing.T) {
	items := summaryLLMPareto(map[string]interface{}{
		"recommendation": map[string]interface{}{
			"variant": "4bit",
			"reason":  "smallest VRAM",
		},
		"variants":        []interface{}{map[string]interface{}{}, map[string]interface{}{}},
		"pareto_frontier": []interface{}{"none", "4bit"},
	})
	if len(items) != 4 {
		t.Fatalf("unexpected item count: %#v", items)
	}
	if items[0].Value != "4bit" {
		t.Fatalf("unexpected recommendation: %#v", items[0])
	}
}

func TestCategoryForPath(t *testing.T) {
	category := categoryForPath("artifacts/eval/vton_comparison/comparison.json", map[string]interface{}{
		"schema_version": "tryops.vton_comparison.v1",
	})
	if category != "vton" {
		t.Fatalf("unexpected category: %q", category)
	}
	configCategory := categoryForPath("artifacts/eval/config/native_config_contract_report.json", map[string]interface{}{
		"schema_version": "tryops.native_config_contract.v1",
	})
	if configCategory != "platform" {
		t.Fatalf("unexpected config category: %q", configCategory)
	}
	postgresCategory := categoryForPath("artifacts/eval/postgres/native_postgres_migration.json", map[string]interface{}{
		"schema_version": "tryops.native_postgres_migration.v1",
	})
	if postgresCategory != "platform" {
		t.Fatalf("unexpected postgres category: %q", postgresCategory)
	}
	backupCategory := categoryForPath("artifacts/eval/backup/native_backup_restore_drill.json", map[string]interface{}{
		"schema_version": "tryops.native_backup_restore_drill.v1",
	})
	if backupCategory != "platform" {
		t.Fatalf("unexpected backup category: %q", backupCategory)
	}
	tlsCategory := categoryForPath("artifacts/eval/tls/native_tls_contract.json", map[string]interface{}{
		"schema_version": "tryops.native_tls_contract.v1",
	})
	if tlsCategory != "platform" {
		t.Fatalf("unexpected tls category: %q", tlsCategory)
	}
	loadCategory := categoryForPath("artifacts/eval/load/native_fullstack_load.json", map[string]interface{}{
		"schema_version": "tryops.native_fullstack_load.v1",
	})
	if loadCategory != "monitoring" {
		t.Fatalf("unexpected load category: %q", loadCategory)
	}
	performanceCategory := categoryForPath("artifacts/eval/performance/native_performance_budget.json", map[string]interface{}{
		"schema_version": "tryops.native_performance_budget.v1",
	})
	if performanceCategory != "monitoring" {
		t.Fatalf("unexpected performance category: %q", performanceCategory)
	}
	traceCategory := categoryForPath("artifacts/eval/trace_envelope/native_trace_envelope_report.json", map[string]interface{}{
		"schema_version": "tryops.native_trace_envelope.v1",
	})
	if traceCategory != "monitoring" {
		t.Fatalf("unexpected trace category: %q", traceCategory)
	}
	runtimeCategory := categoryForPath("artifacts/eval/runtime/native_runtime_telemetry.json", map[string]interface{}{
		"schema_version": "tryops.native_runtime_telemetry.v1",
	})
	if runtimeCategory != "monitoring" {
		t.Fatalf("unexpected runtime category: %q", runtimeCategory)
	}
	observabilityCategory := categoryForPath("artifacts/eval/observability/native_observability_contract.json", map[string]interface{}{
		"schema_version": "tryops.native_observability_contract.v1",
	})
	if observabilityCategory != "monitoring" {
		t.Fatalf("unexpected observability category: %q", observabilityCategory)
	}
	alertmanagerCategory := categoryForPath("artifacts/eval/alerts/native_alertmanager_contract.json", map[string]interface{}{
		"schema_version": "tryops.native_alertmanager_contract.v1",
	})
	if alertmanagerCategory != "monitoring" {
		t.Fatalf("unexpected alertmanager category: %q", alertmanagerCategory)
	}
	ciCategory := categoryForPath("artifacts/eval/ci/native_ci_contract.json", map[string]interface{}{
		"schema_version": "tryops.native_ci_contract.v1",
	})
	if ciCategory != "governance" {
		t.Fatalf("unexpected ci category: %q", ciCategory)
	}
	dependencyCategory := categoryForPath("artifacts/eval/dependencies/native_dependency_lock_contract.json", map[string]interface{}{
		"schema_version": "tryops.native_dependency_lock_contract.v1",
	})
	if dependencyCategory != "governance" {
		t.Fatalf("unexpected dependency category: %q", dependencyCategory)
	}
	containerCategory := categoryForPath("artifacts/eval/containers/native_container_contract_report.json", map[string]interface{}{
		"schema_version": "tryops.native_container_contract.v1",
	})
	if containerCategory != "platform" {
		t.Fatalf("unexpected container category: %q", containerCategory)
	}
	quotaCategory := categoryForPath("artifacts/eval/quota/native_quota_read_model.json", map[string]interface{}{
		"schema_version": "tryops.native_quota_read_model.v1",
	})
	if quotaCategory != "platform" {
		t.Fatalf("unexpected quota category: %q", quotaCategory)
	}
}

func TestSummaryCIContract(t *testing.T) {
	items := summaryCIContract(map[string]interface{}{
		"passed":           true,
		"coverage_level":   "partial_native_ci_supply_chain_contract",
		"production_ready": false,
		"missing_required_tools": []interface{}{
			"syft",
			"trivy",
			"cosign",
		},
		"checks": []interface{}{
			map[string]interface{}{"passed": true},
			map[string]interface{}{"passed": true},
			map[string]interface{}{"passed": false},
		},
	})
	if len(items) != 5 || items[3].Value != "2/3" || items[4].Value != "3" {
		t.Fatalf("unexpected CI summary: %#v", items)
	}
}

func TestSummaryDependencyLock(t *testing.T) {
	items := summaryDependencyLock(map[string]interface{}{
		"passed":         true,
		"coverage_level": "native_dependency_lock_contract",
		"summary": map[string]interface{}{
			"passed_checks": float64(32),
			"total_checks":  float64(32),
			"python_locked": float64(327),
			"node_locked":   float64(92),
			"rust_locked":   float64(188),
			"go_modules":    float64(29),
		},
	})
	if len(items) != 7 || items[2].Value != "32/32" || items[6].Value != "29" {
		t.Fatalf("unexpected dependency lock summary: %#v", items)
	}
}

func TestSummaryPerformanceBudget(t *testing.T) {
	items := summaryPerformanceBudget(map[string]interface{}{
		"passed": true,
		"summary": map[string]interface{}{
			"passed_budgets": float64(11),
			"total_budgets":  float64(11),
			"by_language": map[string]interface{}{
				"rust": float64(4),
				"go":   float64(5),
				"cpp":  float64(2),
			},
		},
	})
	if len(items) != 5 || items[1].Value != "11/11" {
		t.Fatalf("unexpected performance summary: %#v", items)
	}
}

func TestSummaryTraceEnvelope(t *testing.T) {
	items := summaryTraceEnvelope(map[string]interface{}{
		"passed": true,
		"summary": map[string]interface{}{
			"passed_envelopes": float64(4),
			"total_envelopes":  float64(4),
			"by_language": map[string]interface{}{
				"rust":    float64(1),
				"go":      float64(1),
				"cpp":     float64(1),
				"fastapi": float64(1),
			},
		},
	})
	if len(items) != 6 || items[1].Value != "4/4" || items[5].Value != "1" {
		t.Fatalf("unexpected trace envelope summary: %#v", items)
	}
}

func TestSummaryRuntimeTelemetry(t *testing.T) {
	items := summaryRuntimeTelemetry(map[string]interface{}{
		"passed": true,
		"llm": map[string]interface{}{
			"variant_count":    float64(3),
			"max_peak_vram_gb": float64(1.25),
			"benchmark": map[string]interface{}{
				"tokens_per_second": float64(123.5),
			},
		},
		"gpu": map[string]interface{}{
			"devices": []interface{}{map[string]interface{}{"name": "NVIDIA L4"}},
		},
	})
	if len(items) != 5 || items[1].Value != "123.5" || items[4].Value != "1" {
		t.Fatalf("unexpected runtime telemetry summary: %#v", items)
	}
}

func TestSummaryObservabilityContract(t *testing.T) {
	items := summaryObservabilityContract(map[string]interface{}{
		"passed":         true,
		"coverage_level": "partial",
		"summary": map[string]interface{}{
			"passed_checks":       float64(46),
			"total_checks":        float64(46),
			"collector_pipelines": float64(3),
			"correlated_traces":   float64(1),
			"structured_logs":     float64(5),
		},
		"correlation": map[string]interface{}{
			"model_call_observed": true,
		},
	})
	if len(items) != 7 || items[2].Value != "46/46" || items[6].Value != "true" {
		t.Fatalf("unexpected observability summary: %#v", items)
	}
}

func TestSummaryAlertmanagerContract(t *testing.T) {
	items := summaryAlertmanagerContract(map[string]interface{}{
		"passed":         true,
		"coverage_level": "native_alertmanager_routing_contract",
		"summary": map[string]interface{}{
			"passed_checks":  float64(24),
			"total_checks":   float64(24),
			"alert_rules":    float64(16),
			"page_receivers": float64(1),
		},
		"prometheus": map[string]interface{}{
			"alertmanager_targets": []interface{}{"alertmanager:9093"},
		},
	})
	if len(items) != 6 || items[2].Value != "24/24" || items[5].Value != "1" {
		t.Fatalf("unexpected alertmanager summary: %#v", items)
	}
}

func TestSummarySecretRotationContract(t *testing.T) {
	items := summarySecretRotationContract(map[string]interface{}{
		"passed":           true,
		"production_ready": false,
		"coverage_level":   "native_secret_rotation_plan_contract",
		"summary": map[string]interface{}{
			"passed_checks":   float64(34),
			"total_checks":    float64(34),
			"managed_secrets": float64(8),
		},
		"live_readiness": map[string]interface{}{
			"mode": "plan",
		},
	})
	if len(items) != 6 || items[3].Value != "34/34" || items[5].Value != "plan" {
		t.Fatalf("unexpected secret rotation summary: %#v", items)
	}
}

func TestSummaryIncidentWorkflow(t *testing.T) {
	items := summaryIncidentWorkflow(map[string]interface{}{
		"passed":         true,
		"coverage_level": "native_incident_workflow_local_contract",
		"summary": map[string]interface{}{
			"passed_checks":  float64(8),
			"total_checks":   float64(8),
			"timeline_steps": float64(5),
		},
		"incident": map[string]interface{}{
			"status": "resolved",
		},
		"error_tracking": map[string]interface{}{
			"external_tracker": map[string]interface{}{"configured": false},
		},
	})
	if len(items) != 6 || items[2].Value != "8/8" || items[5].Value != "false" {
		t.Fatalf("unexpected incident workflow summary: %#v", items)
	}
}

func TestSummaryContainerContract(t *testing.T) {
	items := summaryContainerContract(map[string]interface{}{
		"passed": true,
		"summary": map[string]interface{}{
			"manifest_roles": float64(7),
			"required_roles": float64(7),
			"compose_roles":  float64(7),
			"by_runtime": map[string]interface{}{
				"go":   float64(3),
				"rust": float64(1),
				"cpp":  float64(1),
			},
		},
	})
	if len(items) != 6 || items[1].Value != "7/7" || items[2].Value != "7" {
		t.Fatalf("unexpected container contract summary: %#v", items)
	}
}

func TestSummaryPostgresMigration(t *testing.T) {
	items := summaryPostgresMigration(map[string]interface{}{
		"passed":         true,
		"coverage_level": "native_postgres_migration_pool_contract",
		"mode":           "plan",
		"summary": map[string]interface{}{
			"total_migrations": float64(2),
			"passed_checks":    float64(18),
			"total_checks":     float64(18),
		},
		"pool": map[string]interface{}{
			"max_conns": float64(8),
		},
	})
	if len(items) != 6 || items[4].Value != "18/18" || items[5].Value != "8" {
		t.Fatalf("unexpected Postgres migration summary: %#v", items)
	}
}

func TestSummaryBackupRestore(t *testing.T) {
	items := summaryBackupRestore(map[string]interface{}{
		"passed":         true,
		"coverage_level": "native_backup_restore_live_drill",
		"mode":           "live",
		"summary": map[string]interface{}{
			"passed_checks":            float64(32),
			"total_checks":             float64(32),
			"postgres_restored_tables": float64(7),
			"minio_restored_objects":   float64(1),
		},
	})
	if len(items) != 6 || items[3].Value != "32/32" || items[4].Value != "7" || items[5].Value != "1" {
		t.Fatalf("unexpected backup restore summary: %#v", items)
	}
}

func TestSummaryTLSContract(t *testing.T) {
	items := summaryTLSContract(map[string]interface{}{
		"passed":         true,
		"coverage_level": "native_tls_termination_live_handshake",
		"mode":           "live",
		"summary": map[string]interface{}{
			"passed_checks": float64(30),
			"total_checks":  float64(30),
			"https_health":  true,
		},
		"live": map[string]interface{}{
			"tls_version": "TLS1.3",
		},
	})
	if len(items) != 6 || items[3].Value != "30/30" || items[4].Value != "TLS1.3" || items[5].Value != "true" {
		t.Fatalf("unexpected TLS summary: %#v", items)
	}
}

func TestSummaryNativeFullstackLoad(t *testing.T) {
	items := summaryNativeFullstackLoad(map[string]interface{}{
		"passed":         true,
		"coverage_level": "native_go_fullstack_gateway_bff_load_slo",
		"summary": map[string]interface{}{
			"passed_scenarios": float64(6),
			"total_scenarios":  float64(6),
			"total_requests":   float64(504),
			"total_errors":     float64(0),
			"worst_p95_ms":     float64(36.473),
			"external_ready":   true,
		},
	})
	if len(items) != 7 || items[2].Value != "6/6" || items[5].Value != "36.473" {
		t.Fatalf("unexpected fullstack load summary: %#v", items)
	}
}

func TestSummaryQuotaReadModel(t *testing.T) {
	items := summaryQuotaReadModel(map[string]interface{}{
		"passed": true,
		"summary": map[string]interface{}{
			"tenants":       float64(1),
			"periods":       float64(1),
			"showback_usd":  float64(0.012),
			"native_source": true,
		},
	})
	if len(items) != 5 || items[1].Value != "1" || items[4].Value != "true" {
		t.Fatalf("unexpected quota read model summary: %#v", items)
	}
}

func TestSelectHighlightsIncludesTraceEnvelope(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_trace_envelope_report",
			Path:          "artifacts/eval/trace_envelope/native_trace_envelope_report.json",
			SchemaVersion: "tryops.native_trace_envelope.v1",
		},
	})
	report, ok := highlights["trace_envelope"]
	if !ok || report.SchemaVersion != "tryops.native_trace_envelope.v1" {
		t.Fatalf("expected trace envelope highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesContainerContract(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_container_contract_report",
			Path:          "artifacts/eval/containers/native_container_contract_report.json",
			SchemaVersion: "tryops.native_container_contract.v1",
		},
	})
	report, ok := highlights["container_contract"]
	if !ok || report.SchemaVersion != "tryops.native_container_contract.v1" {
		t.Fatalf("expected container contract highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesBackupRestore(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_backup_restore_live",
			Path:          "artifacts/eval/backup/native_backup_restore_live.json",
			SchemaVersion: "tryops.native_backup_restore_drill.v1",
		},
	})
	report, ok := highlights["backup_restore"]
	if !ok || report.SchemaVersion != "tryops.native_backup_restore_drill.v1" {
		t.Fatalf("expected backup restore highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesTLSContract(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_tls_contract_live",
			Path:          "artifacts/eval/tls/native_tls_contract_live.json",
			SchemaVersion: "tryops.native_tls_contract.v1",
		},
	})
	report, ok := highlights["tls_contract"]
	if !ok || report.SchemaVersion != "tryops.native_tls_contract.v1" {
		t.Fatalf("expected TLS contract highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesFullstackLoad(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_fullstack_load",
			Path:          "artifacts/eval/load/native_fullstack_load.json",
			SchemaVersion: "tryops.native_fullstack_load.v1",
		},
	})
	report, ok := highlights["fullstack_load"]
	if !ok || report.SchemaVersion != "tryops.native_fullstack_load.v1" {
		t.Fatalf("expected fullstack load highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesCIContract(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_ci_contract",
			Path:          "artifacts/eval/ci/native_ci_contract.json",
			SchemaVersion: "tryops.native_ci_contract.v1",
		},
	})
	report, ok := highlights["ci_contract"]
	if !ok || report.SchemaVersion != "tryops.native_ci_contract.v1" {
		t.Fatalf("expected CI contract highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesDependencyLock(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_dependency_lock_contract",
			Path:          "artifacts/eval/dependencies/native_dependency_lock_contract.json",
			SchemaVersion: "tryops.native_dependency_lock_contract.v1",
		},
	})
	report, ok := highlights["dependency_lock"]
	if !ok || report.SchemaVersion != "tryops.native_dependency_lock_contract.v1" {
		t.Fatalf("expected dependency lock highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesQuotaReadModel(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_quota_read_model",
			Path:          "artifacts/eval/quota/native_quota_read_model.json",
			SchemaVersion: "tryops.native_quota_read_model.v1",
		},
	})
	report, ok := highlights["quota_read_model"]
	if !ok || report.SchemaVersion != "tryops.native_quota_read_model.v1" {
		t.Fatalf("expected quota read model highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesDistributedQuota(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_distributed_quota_admission",
			Path:          "artifacts/eval/quota/native_distributed_quota_admission.json",
			SchemaVersion: "tryops.distributed_quota_admission.v1",
		},
	})
	report, ok := highlights["distributed_quota"]
	if !ok || report.SchemaVersion != "tryops.distributed_quota_admission.v1" {
		t.Fatalf("expected distributed quota highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesRuntimeTelemetry(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_runtime_telemetry",
			Path:          "artifacts/eval/runtime/native_runtime_telemetry.json",
			SchemaVersion: "tryops.native_runtime_telemetry.v1",
		},
	})
	report, ok := highlights["runtime_telemetry"]
	if !ok || report.SchemaVersion != "tryops.native_runtime_telemetry.v1" {
		t.Fatalf("expected runtime telemetry highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesObservabilityContract(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_observability_contract",
			Path:          "artifacts/eval/observability/native_observability_contract.json",
			SchemaVersion: "tryops.native_observability_contract.v1",
		},
	})
	report, ok := highlights["observability"]
	if !ok || report.SchemaVersion != "tryops.native_observability_contract.v1" {
		t.Fatalf("expected observability highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesAlertmanagerContract(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_alertmanager_contract",
			Path:          "artifacts/eval/alerts/native_alertmanager_contract.json",
			SchemaVersion: "tryops.native_alertmanager_contract.v1",
		},
	})
	report, ok := highlights["alertmanager"]
	if !ok || report.SchemaVersion != "tryops.native_alertmanager_contract.v1" {
		t.Fatalf("expected alertmanager highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesIncidentWorkflow(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_incident_workflow",
			Path:          "artifacts/eval/incidents/native_incident_workflow.json",
			SchemaVersion: "tryops.native_incident_workflow.v1",
		},
	})
	report, ok := highlights["incident_workflow"]
	if !ok || report.SchemaVersion != "tryops.native_incident_workflow.v1" {
		t.Fatalf("expected incident workflow highlight: %#v", highlights)
	}
}

func TestSelectHighlightsIncludesSecretRotation(t *testing.T) {
	highlights := selectHighlights([]artifactReport{
		{
			Name:          "native_secret_rotation_contract",
			Path:          "artifacts/eval/secrets/native_secret_rotation_contract.json",
			SchemaVersion: "tryops.native_secret_rotation_contract.v1",
		},
	})
	report, ok := highlights["secret_rotation"]
	if !ok || report.SchemaVersion != "tryops.native_secret_rotation_contract.v1" {
		t.Fatalf("expected secret rotation highlight: %#v", highlights)
	}
}

func TestSummaryVTONNativeAPI(t *testing.T) {
	items := summaryVTONNativeAPI(map[string]interface{}{
		"passed": true,
		"checks": []interface{}{
			map[string]interface{}{"name": "native_preprocess_person_available", "passed": true},
			map[string]interface{}{"name": "native_image_metrics_available", "passed": true},
		},
		"native_vton": map[string]interface{}{
			"quality_score": float64(0.875),
			"preprocessing": map[string]interface{}{"available": true},
			"image_metrics": map[string]interface{}{"available": true},
		},
	})
	if len(items) != 5 || items[1].Value != "2/2" || items[4].Value != "0.875" {
		t.Fatalf("unexpected native VTON API summary: %#v", items)
	}
}

func TestBuildPipelineRunsCombinesRunContextOpenLineageAndLineage(t *testing.T) {
	root := t.TempDir()
	runDir := filepath.Join(root, "reports", "generated", "candidate-1")
	if err := os.MkdirAll(runDir, 0o755); err != nil {
		t.Fatal(err)
	}
	writeTestJSON(t, filepath.Join(runDir, "run_context.json"), `{
		"schema_version":"tryops.run_context.v1",
		"run_id":"run-1",
		"run_name":"local-promotion-pipeline",
		"trace_id":"trace-1",
		"code":{"version":"local-dev"}
	}`)
	writeTestJSON(t, filepath.Join(runDir, "openlineage_run_event.json"), `{
		"eventType":"COMPLETE",
		"eventTime":"2026-06-11T00:00:00Z",
		"job":{"name":"vton.local-promotion-pipeline","facets":{"tryopsJob":{"workload":"vton","modelName":"catvton","modelVersion":"0.1.0"}}},
		"run":{"runId":"openlineage-run","facets":{"tryopsRun":{"candidateId":"candidate-1","riskStatus":"approved","signed":true,"traceId":"trace-1"}}},
		"inputs":[{"facets":{"tryopsDataset":{"datasetVersion":"dataset-v1"}}}]
	}`)
	writeTestJSON(t, filepath.Join(runDir, "lineage.json"), `{
		"schema_version":"tryops.lineage.v1",
		"candidate_id":"candidate-1",
		"workload":"vton",
		"risk_status":"approved",
		"model":{"name":"catvton","version":"0.1.0","signed":true},
		"lineage":{"dataset_version":"dataset-v1","pipeline_run_id":"run-1","code_version":"local-dev"}
	}`)

	runs := buildPipelineRuns(root)
	if len(runs) != 1 {
		t.Fatalf("unexpected run count: %#v", runs)
	}
	run := runs[0]
	if run.RunID != "run-1" || run.EventType != "COMPLETE" || run.DatasetVersion != "dataset-v1" {
		t.Fatalf("unexpected run: %#v", run)
	}
	if run.Paths["run_context"] != "reports/generated/candidate-1/run_context.json" {
		t.Fatalf("unexpected paths: %#v", run.Paths)
	}
}

func TestBuildOptimizationPanelCombinesParetoLeaderboardAndEnergy(t *testing.T) {
	root := t.TempDir()
	writeTestJSON(t, filepath.Join(root, "artifacts", "eval", "llm_pareto", "pareto.json"), `{
		"schema_version":"tryops.llm_pareto.v1",
		"model_id":"model-a",
		"pareto_frontier":["none","4bit"],
		"recommendation":{"variant":"4bit","reason":"smallest VRAM"},
		"variants":[
			{"variant":"none","adapter":"transformers-none","quality_score":0.25,"latency_p50_ms":10,"tokens_per_second":20,"peak_vram_gb":1.0,"slo":{"verdict":"pass"}},
			{"variant":"4bit","adapter":"transformers-4bit","quality_score":0.28,"latency_p50_ms":20,"tokens_per_second":12,"peak_vram_gb":0.5,"slo":{"verdict":"pass"}}
		]
	}`)
	writeTestJSON(t, filepath.Join(root, "artifacts", "eval", "leaderboard", "leaderboard.json"), `{
		"schema_version":"tryops.eval_leaderboard.v1",
		"judge_backend":"offline-rubric",
		"ranking":["baseline","4bit","none"],
		"leaderboard":[
			{"variant":"baseline","quality":0.83},
			{"variant":"4bit","quality":0.28,"slo_verdict":"pass"},
			{"variant":"none","quality":0.25,"slo_verdict":"pass"}
		]
	}`)
	writeTestJSON(t, filepath.Join(root, "artifacts", "eval", "energy", "energy_sweep.json"), `{
		"schema_version":"tryops.energy_report.v1",
		"carbon_gate":{"verdict":"pass","greenest_variant":"none"},
		"variants":[
			{"variant":"none","energy_wh_per_1k_tokens":0.4,"sci_g_per_1k_tokens":0.2},
			{"variant":"4bit","energy_wh_per_1k_tokens":0.7,"sci_g_per_1k_tokens":0.3}
		]
	}`)

	panel := buildOptimizationPanel(root)
	if panel == nil {
		t.Fatal("expected optimization panel")
	}
	if panel.RecommendedVariant != "4bit" || panel.CarbonGateVerdict != "pass" {
		t.Fatalf("unexpected panel: %#v", panel)
	}
	if len(panel.Variants) != 3 || panel.Variants[1].Variant != "4bit" || !panel.Variants[1].Recommended {
		t.Fatalf("unexpected variants: %#v", panel.Variants)
	}
}

func writeTestJSON(t *testing.T, path string, body string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}
