package main

import (
	"path/filepath"
	"strings"
)

func buildReport(root string, path string, data map[string]interface{}) artifactReport {
	rel := relPath(root, path)
	name := strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))
	report := artifactReport{
		Name:          name,
		Title:         titleForPath(rel, data),
		Category:      categoryForPath(rel, data),
		Path:          rel,
		SchemaVersion: stringField(data, "schema_version"),
		CreatedAt:     createdAt(data),
		Status:        statusForReport(rel, data),
		Summary:       summaryForReport(rel, data),
		Metadata:      metadataForReport(data),
	}
	return report
}

func categoryForPath(path string, data map[string]interface{}) string {
	schema := stringField(data, "schema_version")
	switch {
	case strings.Contains(path, "/llm_") || strings.Contains(path, "/leaderboard/") || strings.Contains(schema, "llm"):
		return "llm"
	case strings.Contains(path, "/vton_") || strings.Contains(schema, "vton"):
		return "vton"
	case strings.Contains(path, "/energy/") || strings.Contains(schema, "energy"):
		return "sustainability"
	case strings.Contains(path, "/drift/") || strings.Contains(path, "/slo/") || strings.Contains(path, "/load/") || strings.Contains(path, "/performance/") || strings.Contains(path, "/runtime/") || strings.Contains(path, "/trace_envelope/") || strings.Contains(path, "/observability/") || strings.Contains(path, "/alerts/") || strings.Contains(path, "/incidents/") || strings.Contains(schema, "drift") || strings.Contains(schema, "slo_gate") || strings.Contains(schema, "native_fullstack_load") || strings.Contains(schema, "performance_budget") || strings.Contains(schema, "runtime_telemetry") || strings.Contains(schema, "trace_envelope") || strings.Contains(schema, "observability_contract") || strings.Contains(schema, "alertmanager_contract") || strings.Contains(schema, "incident_workflow"):
		return "monitoring"
	case strings.Contains(path, "/config/") || strings.Contains(path, "/containers/") || strings.Contains(path, "/quota/") || strings.Contains(path, "/postgres/") || strings.Contains(path, "/backup/") || strings.Contains(path, "/tls/") || strings.Contains(schema, "config_contract") || strings.Contains(schema, "container_contract") || strings.Contains(schema, "quota_read_model") || strings.Contains(schema, "postgres_migration") || strings.Contains(schema, "backup_restore") || strings.Contains(schema, "tls_contract"):
		return "platform"
	case strings.Contains(path, "/data_versioning/") || strings.Contains(schema, "dvc_minio"):
		return "platform"
	case strings.Contains(path, "/governance/") || strings.Contains(path, "/guardrails/") || strings.Contains(path, "/security/") || strings.Contains(path, "/supply_chain/") || strings.Contains(path, "/events/") || strings.Contains(path, "/ci/") || strings.Contains(schema, "vulnerability") || strings.Contains(schema, "ci_contract") || strings.Contains(schema, "event_dispatcher"):
		return "governance"
	case strings.Contains(path, "/full_stack/") || strings.Contains(path, "/demo_acceptance/") || strings.Contains(path, "/demo_video/") || strings.Contains(path, "/endpoint_smoke/") || strings.Contains(schema, "job_runner") || strings.Contains(schema, "professor_demo_video"):
		return "acceptance"
	case strings.Contains(path, "/deployments/") || strings.Contains(path, "/rollback"):
		return "release"
	default:
		return "platform"
	}
}

func titleForPath(path string, data map[string]interface{}) string {
	schema := stringField(data, "schema_version")
	switch schema {
	case "tryops.llm_pareto.v1":
		return "LLM quantization Pareto"
	case "tryops.energy_report.v1":
		return "Energy and carbon report"
	case "tryops.vton_comparison.v1":
		return "VTON comparison gallery"
	case "tryops.vton_native_api.v1":
		return "Native VTON API integration"
	case "tryops.drift_summary.v1":
		return "Drift summary"
	case "tryops.full_stack_smoke.v1":
		return "Full-stack startup smoke"
	case "tryops.professor_demo_acceptance.v1":
		return "Professor demo acceptance"
	case "tryops.professor_demo_video.v1":
		return "Professor demo backup video"
	case "tryops.native_job_runner.v1":
		return "Native Go job runner"
	case "tryops.vulnerability_scan.v1":
		return "Vulnerability scan coverage"
	case "tryops.native_ci_contract.v1":
		return "Native CI supply-chain contract"
	case "tryops.native_slo_gate.v1":
		return "Native SLO regression gate"
	case "tryops.native_event_dispatcher.v1":
		return "Native event dispatcher"
	case "tryops.dvc_minio_versioning.v1":
		return "DVC/MinIO data versioning"
	case "tryops.garment_similarity.v1":
		return "CLIP garment similarity"
	case "tryops.native_gguf_preflight.v1":
		return "GGUF CPU preflight"
	case "tryops.quantized_model_preflight.v1":
		return "GPTQ/AWQ model preflight"
	case "tryops.vllm_serving_probe.v1":
		return "vLLM serving probe"
	case "tryops.native_config_contract.v1":
		return "Native config contract"
	case "tryops.native_postgres_migration.v1":
		return "Native Postgres migration and pool"
	case "tryops.native_backup_restore_drill.v1":
		return "Native backup/restore drill"
	case "tryops.native_tls_contract.v1":
		return "Native TLS termination"
	case "tryops.native_fullstack_load.v1":
		return "Native full-stack load SLO"
	case "tryops.native_container_contract.v1":
		return "Native container image split"
	case "tryops.native_quota_read_model.v1":
		return "Native quota read model"
	case "tryops.native_performance_budget.v1":
		return "Native performance budget"
	case "tryops.native_runtime_telemetry.v1":
		return "Native runtime telemetry"
	case "tryops.native_trace_envelope.v1":
		return "Native trace/log envelope"
	case "tryops.native_observability_contract.v1":
		return "Native observability contract"
	case "tryops.native_alertmanager_contract.v1":
		return "Native Alertmanager routing"
	case "tryops.native_incident_workflow.v1":
		return "Native incident workflow"
	}
	base := strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))
	base = strings.ReplaceAll(base, "_", " ")
	return strings.Title(base)
}

func statusForReport(path string, data map[string]interface{}) string {
	schema := stringField(data, "schema_version")
	if coverage := stringField(data, "coverage_level"); coverage != "" {
		if ready, ok := boolField(data, "production_ready"); ok && !ready {
			return coverage
		}
	}
	if schema == "tryops.llm_pareto.v1" && objectField(data, "recommendation") != nil {
		return "passed"
	}
	if schema == "tryops.energy_report.v1" {
		gate := objectField(data, "carbon_gate")
		if stringField(gate, "verdict") == "pass" {
			return "passed"
		}
	}
	if schema == "tryops.vton_comparison.v1" && len(arrayField(data, "runs")) > 0 {
		return "passed"
	}
	if schema == "tryops.garment_similarity.v1" && boolFieldDefault(objectField(data, "clip"), "available") {
		return "passed"
	}
	if schema == "tryops.vllm_serving_probe.v1" {
		if status := stringField(data, "status"); status != "" {
			return status
		}
	}
	if schema == "tryops.quantized_model_preflight.v1" {
		if status := stringField(data, "status"); status != "" {
			return status
		}
	}
	if passed, ok := boolField(data, "passed"); ok {
		if passed {
			return "passed"
		}
		return "failed"
	}
	if approved, ok := boolField(data, "approved"); ok {
		if approved {
			return "approved"
		}
		return "blocked"
	}
	if drift, ok := boolField(data, "any_drift_detected"); ok && drift {
		return "warning"
	}
	if drift, ok := boolField(data, "drift_detected"); ok && drift {
		return "warning"
	}
	if status := stringField(data, "status"); status != "" {
		return status
	}
	if strings.Contains(path, "error") {
		return "warning"
	}
	return "recorded"
}

func createdAt(data map[string]interface{}) string {
	for _, key := range []string{"created_at", "generated_at"} {
		if value := stringField(data, key); value != "" {
			return value
		}
	}
	return ""
}

func metadataForReport(data map[string]interface{}) map[string]string {
	meta := map[string]string{}
	for _, key := range []string{"workload", "model_id", "candidate_id", "package_id", "coverage_level"} {
		if value := stringField(data, key); value != "" {
			meta[key] = value
		}
	}
	if len(meta) == 0 {
		return nil
	}
	return meta
}
