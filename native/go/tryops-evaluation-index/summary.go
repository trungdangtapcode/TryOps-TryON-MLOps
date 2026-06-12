package main

import "fmt"

func summaryForReport(path string, data map[string]interface{}) []summaryItem {
	switch stringField(data, "schema_version") {
	case "tryops.llm_pareto.v1":
		return summaryLLMPareto(data)
	case "tryops.energy_report.v1":
		return summaryEnergy(data)
	case "tryops.vton_comparison.v1":
		return summaryVTONComparison(data)
	case "tryops.vton_native_api.v1":
		return summaryVTONNativeAPI(data)
	case "tryops.drift_summary.v1":
		return summaryDrift(data)
	case "tryops.full_stack_smoke.v1", "tryops.professor_demo_acceptance.v1":
		return summaryChecks(data)
	case "tryops.professor_demo_video.v1":
		return summaryProfessorDemoVideo(data)
	case "tryops.native_job_runner.v1":
		return summaryNativeJobRunner(data)
	case "tryops.native_slo_gate.v1":
		return summaryNativeSLOGate(data)
	case "tryops.native_event_dispatcher.v1":
		return summaryNativeEventDispatcher(data)
	case "tryops.dvc_minio_versioning.v1":
		return summaryDVCMinIO(data)
	case "tryops.garment_similarity.v1":
		return summaryGarmentSimilarity(data)
	case "tryops.native_gguf_preflight.v1":
		return summaryGGUFPreflight(data)
	case "tryops.quantized_model_preflight.v1":
		return summaryQuantizedPreflight(data)
	case "tryops.vllm_serving_probe.v1":
		return summaryVLLMProbe(data)
	case "tryops.vulnerability_scan.v1":
		return summaryVulnerability(data)
	case "tryops.native_ci_contract.v1":
		return summaryCIContract(data)
	case "tryops.native_config_contract.v1":
		return summaryConfigContract(data)
	case "tryops.native_postgres_migration.v1":
		return summaryPostgresMigration(data)
	case "tryops.native_backup_restore_drill.v1":
		return summaryBackupRestore(data)
	case "tryops.native_tls_contract.v1":
		return summaryTLSContract(data)
	case "tryops.native_fullstack_load.v1":
		return summaryNativeFullstackLoad(data)
	case "tryops.native_container_contract.v1":
		return summaryContainerContract(data)
	case "tryops.native_quota_read_model.v1":
		return summaryQuotaReadModel(data)
	case "tryops.native_performance_budget.v1":
		return summaryPerformanceBudget(data)
	case "tryops.native_runtime_telemetry.v1":
		return summaryRuntimeTelemetry(data)
	case "tryops.native_trace_envelope.v1":
		return summaryTraceEnvelope(data)
	case "tryops.native_observability_contract.v1":
		return summaryObservabilityContract(data)
	case "tryops.native_alertmanager_contract.v1":
		return summaryAlertmanagerContract(data)
	case "tryops.native_incident_workflow.v1":
		return summaryIncidentWorkflow(data)
	}
	items := make([]summaryItem, 0, 4)
	for _, key := range []string{"passed", "approved", "status", "verdict", "workload", "model_id"} {
		if value, ok := formatScalar(data[key]); ok {
			items = append(items, summaryItem{Label: key, Value: value})
		}
	}
	if len(items) == 0 {
		items = append(items, summaryItem{Label: "path", Value: path})
	}
	return items
}

func summaryLLMPareto(data map[string]interface{}) []summaryItem {
	recommendation := objectField(data, "recommendation")
	return []summaryItem{
		{Label: "recommended variant", Value: stringField(recommendation, "variant")},
		{Label: "reason", Value: stringField(recommendation, "reason")},
		{Label: "variants", Value: fmt.Sprintf("%d", len(arrayField(data, "variants")))},
		{Label: "pareto frontier", Value: fmt.Sprintf("%d", len(arrayField(data, "pareto_frontier")))},
	}
}

func summaryEnergy(data map[string]interface{}) []summaryItem {
	gate := objectField(data, "carbon_gate")
	return []summaryItem{
		{Label: "carbon gate", Value: stringField(gate, "verdict")},
		{Label: "greenest variant", Value: stringField(gate, "greenest_variant")},
		{Label: "variants", Value: fmt.Sprintf("%d", len(arrayField(data, "variants")))},
		{Label: "mode", Value: stringField(data, "mode")},
	}
}

func summaryVTONComparison(data map[string]interface{}) []summaryItem {
	return []summaryItem{
		{Label: "runs", Value: fmt.Sprintf("%d", len(arrayField(data, "runs")))},
		{Label: "structural winner", Value: stringField(data, "winner_by_structural_similarity")},
		{Label: "garment winner", Value: stringField(data, "winner_by_garment_similarity_proxy")},
	}
}

func summaryVTONNativeAPI(data map[string]interface{}) []summaryItem {
	native := objectField(data, "native_vton")
	preprocessing := objectField(native, "preprocessing")
	imageMetrics := objectField(native, "image_metrics")
	checks := arrayField(data, "checks")
	passedChecks := 0
	for _, item := range checks {
		check, _ := item.(map[string]interface{})
		if boolFieldDefault(check, "passed") {
			passedChecks++
		}
	}
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "checks", Value: fmt.Sprintf("%d/%d", passedChecks, len(checks))},
		{Label: "preprocess", Value: formatValue(preprocessing["available"])},
		{Label: "image metrics", Value: formatValue(imageMetrics["available"])},
		{Label: "quality", Value: formatValue(native["quality_score"])},
	}
}

func summaryDrift(data map[string]interface{}) []summaryItem {
	return []summaryItem{
		{Label: "any drift detected", Value: formatValue(data["any_drift_detected"])},
		{Label: "reports", Value: fmt.Sprintf("%d", len(objectField(data, "reports")))},
	}
}

func summaryChecks(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	checks := arrayField(data, "checks")
	if len(checks) == 0 {
		checks = arrayField(data, "evidence")
	}
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "checks", Value: fmt.Sprintf("%d", len(checks))},
		{Label: "passed checks", Value: formatValue(summary["passed_checks"])},
		{Label: "failed checks", Value: formatValue(summary["failed_checks"])},
	}
}

func summaryNativeJobRunner(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "jobs", Value: formatValue(summary["total"])},
		{Label: "passed jobs", Value: formatValue(summary["passed"])},
		{Label: "failed jobs", Value: formatValue(summary["failed"])},
	}
}

func summaryProfessorDemoVideo(data map[string]interface{}) []summaryItem {
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "duration", Value: formatValue(data["duration_seconds"]) + " sec"},
		{Label: "frames", Value: formatValue(data["frame_count"])},
		{Label: "video bytes", Value: formatValue(data["video_bytes"])},
	}
}

func summaryNativeSLOGate(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "rules", Value: formatValue(summary["total_rules"])},
		{Label: "passed rules", Value: formatValue(summary["passed_rules"])},
		{Label: "failed rules", Value: formatValue(summary["failed_rules"])},
	}
}

func summaryNativeEventDispatcher(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "events", Value: formatValue(summary["events"])},
		{Label: "audit written", Value: formatValue(summary["audit_written"])},
		{Label: "webhook delivered", Value: formatValue(summary["webhook_delivered"])},
	}
}

func summaryDVCMinIO(data map[string]interface{}) []summaryItem {
	localCache := objectField(data, "local_cache")
	remoteCache := objectField(data, "remote_cache")
	remote := objectField(data, "remote")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "local objects", Value: formatValue(localCache["count"])},
		{Label: "remote objects", Value: formatValue(remoteCache["count"])},
		{Label: "bucket", Value: stringField(remote, "bucket")},
	}
}

func summaryGarmentSimilarity(data map[string]interface{}) []summaryItem {
	clip := objectField(data, "clip")
	proxy := objectField(data, "proxy")
	bestText := objectField(clip, "best_text_prompt")
	return []summaryItem{
		{Label: "clip available", Value: formatValue(clip["available"])},
		{Label: "backend", Value: stringField(clip, "backend")},
		{Label: "image similarity", Value: formatValue(clip["image_similarity"])},
		{Label: "proxy score", Value: formatValue(proxy["score"])},
		{Label: "best prompt", Value: stringField(bestText, "prompt")},
	}
}

func summaryGGUFPreflight(data map[string]interface{}) []summaryItem {
	header := objectField(data, "header")
	selected := objectField(data, "selected_metadata")
	runtime := objectField(data, "runtime")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "architecture", Value: stringField(selected, "general.architecture")},
		{Label: "file type", Value: stringField(selected, "general.file_type_name")},
		{Label: "tensors", Value: formatValue(header["tensor_count"])},
		{Label: "llama cli", Value: formatValue(runtime["llama_cli_available"])},
	}
}

func summaryQuantizedPreflight(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	return []summaryItem{
		{Label: "status", Value: stringField(data, "status")},
		{Label: "suitable", Value: formatValue(summary["suitable_candidates"]) + "/" + formatValue(summary["total_candidates"])},
		{Label: "load ready", Value: formatValue(summary["load_ready_candidates"]) + "/" + formatValue(summary["total_candidates"])},
		{Label: "gptq", Value: stringField(summary, "gptq_status")},
		{Label: "awq", Value: stringField(summary, "awq_status")},
	}
}

func summaryVLLMProbe(data map[string]interface{}) []summaryItem {
	target := objectField(data, "target")
	env := objectField(data, "environment")
	load := objectField(data, "load")
	return []summaryItem{
		{Label: "status", Value: stringField(data, "status")},
		{Label: "model", Value: stringField(target, "model")},
		{Label: "vllm binary", Value: formatValue(env["vllm_binary_available"])},
		{Label: "succeeded", Value: formatValue(load["succeeded"])},
		{Label: "tokens/sec", Value: formatValue(load["tokens_per_second"])},
	}
}

func summaryVulnerability(data map[string]interface{}) []summaryItem {
	missing := arrayField(data, "missing_required_tools")
	return []summaryItem{
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "production ready", Value: formatValue(data["production_ready"])},
		{Label: "missing tools", Value: fmt.Sprintf("%d", len(missing))},
	}
}

func summaryCIContract(data map[string]interface{}) []summaryItem {
	missing := arrayField(data, "missing_required_tools")
	checks := arrayField(data, "checks")
	passedChecks := 0
	for _, item := range checks {
		check, _ := item.(map[string]interface{})
		if boolFieldDefault(check, "passed") {
			passedChecks++
		}
	}
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "production ready", Value: formatValue(data["production_ready"])},
		{Label: "checks", Value: fmt.Sprintf("%d/%d", passedChecks, len(checks))},
		{Label: "missing tools", Value: fmt.Sprintf("%d", len(missing))},
	}
}

func summaryConfigContract(data map[string]interface{}) []summaryItem {
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "services", Value: fmt.Sprintf("%d", len(arrayField(data, "services")))},
		{Label: "secrets", Value: fmt.Sprintf("%d", len(arrayField(data, "secrets")))},
		{Label: "checks", Value: fmt.Sprintf("%d", len(arrayField(data, "checks")))},
	}
}

func summaryPostgresMigration(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	pool := objectField(data, "pool")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "mode", Value: stringField(data, "mode")},
		{Label: "migrations", Value: formatValue(summary["total_migrations"])},
		{Label: "checks", Value: formatValue(summary["passed_checks"]) + "/" + formatValue(summary["total_checks"])},
		{Label: "pool max", Value: formatValue(pool["max_conns"])},
	}
}

func summaryBackupRestore(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "mode", Value: stringField(data, "mode")},
		{Label: "checks", Value: formatValue(summary["passed_checks"]) + "/" + formatValue(summary["total_checks"])},
		{Label: "pg tables", Value: formatValue(summary["postgres_restored_tables"])},
		{Label: "minio objects", Value: formatValue(summary["minio_restored_objects"])},
	}
}

func summaryTLSContract(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	live := objectField(data, "live")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "mode", Value: stringField(data, "mode")},
		{Label: "checks", Value: formatValue(summary["passed_checks"]) + "/" + formatValue(summary["total_checks"])},
		{Label: "tls", Value: stringField(live, "tls_version")},
		{Label: "https health", Value: formatValue(summary["https_health"])},
	}
}

func summaryNativeFullstackLoad(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "scenarios", Value: formatValue(summary["passed_scenarios"]) + "/" + formatValue(summary["total_scenarios"])},
		{Label: "requests", Value: formatValue(summary["total_requests"])},
		{Label: "errors", Value: formatValue(summary["total_errors"])},
		{Label: "worst p95 ms", Value: formatValue(summary["worst_p95_ms"])},
		{Label: "external ready", Value: formatValue(summary["external_ready"])},
	}
}

func summaryContainerContract(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	byRuntime := objectField(summary, "by_runtime")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "roles", Value: formatValue(summary["manifest_roles"]) + "/" + formatValue(summary["required_roles"])},
		{Label: "compose roles", Value: formatValue(summary["compose_roles"])},
		{Label: "go", Value: formatValue(byRuntime["go"])},
		{Label: "rust", Value: formatValue(byRuntime["rust"])},
		{Label: "cpp", Value: formatValue(byRuntime["cpp"])},
	}
}

func summaryQuotaReadModel(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "tenants", Value: formatValue(summary["tenants"])},
		{Label: "periods", Value: formatValue(summary["periods"])},
		{Label: "showback", Value: formatValue(summary["showback_usd"])},
		{Label: "native source", Value: formatValue(summary["native_source"])},
	}
}

func summaryPerformanceBudget(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	byLanguage := objectField(summary, "by_language")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "budgets", Value: formatValue(summary["passed_budgets"]) + "/" + formatValue(summary["total_budgets"])},
		{Label: "rust", Value: formatValue(byLanguage["rust"])},
		{Label: "go", Value: formatValue(byLanguage["go"])},
		{Label: "cpp", Value: formatValue(byLanguage["cpp"])},
	}
}

func summaryRuntimeTelemetry(data map[string]interface{}) []summaryItem {
	llm := objectField(data, "llm")
	benchmark := objectField(llm, "benchmark")
	gpu := objectField(data, "gpu")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "benchmark tps", Value: formatValue(benchmark["tokens_per_second"])},
		{Label: "variants", Value: formatValue(llm["variant_count"])},
		{Label: "max vram gb", Value: formatValue(llm["max_peak_vram_gb"])},
		{Label: "gpus", Value: fmt.Sprintf("%d", len(arrayField(gpu, "devices")))},
	}
}

func summaryTraceEnvelope(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	byLanguage := objectField(summary, "by_language")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "envelopes", Value: formatValue(summary["passed_envelopes"]) + "/" + formatValue(summary["total_envelopes"])},
		{Label: "rust", Value: formatValue(byLanguage["rust"])},
		{Label: "go", Value: formatValue(byLanguage["go"])},
		{Label: "cpp", Value: formatValue(byLanguage["cpp"])},
		{Label: "fastapi", Value: formatValue(byLanguage["fastapi"])},
	}
}

func summaryObservabilityContract(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	correlation := objectField(data, "correlation")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "checks", Value: formatValue(summary["passed_checks"]) + "/" + formatValue(summary["total_checks"])},
		{Label: "pipelines", Value: formatValue(summary["collector_pipelines"])},
		{Label: "shared traces", Value: formatValue(summary["correlated_traces"])},
		{Label: "structured logs", Value: formatValue(summary["structured_logs"])},
		{Label: "model call", Value: formatValue(correlation["model_call_observed"])},
	}
}

func summaryAlertmanagerContract(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	prometheus := objectField(data, "prometheus")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "checks", Value: formatValue(summary["passed_checks"]) + "/" + formatValue(summary["total_checks"])},
		{Label: "rules", Value: formatValue(summary["alert_rules"])},
		{Label: "page receivers", Value: formatValue(summary["page_receivers"])},
		{Label: "targets", Value: fmt.Sprintf("%d", len(arrayField(prometheus, "alertmanager_targets")))},
	}
}

func summaryIncidentWorkflow(data map[string]interface{}) []summaryItem {
	summary := objectField(data, "summary")
	incident := objectField(data, "incident")
	errorTracking := objectField(data, "error_tracking")
	external := objectField(errorTracking, "external_tracker")
	return []summaryItem{
		{Label: "passed", Value: formatValue(data["passed"])},
		{Label: "coverage", Value: stringField(data, "coverage_level")},
		{Label: "checks", Value: formatValue(summary["passed_checks"]) + "/" + formatValue(summary["total_checks"])},
		{Label: "status", Value: stringField(incident, "status")},
		{Label: "timeline", Value: formatValue(summary["timeline_steps"])},
		{Label: "external tracker", Value: formatValue(external["configured"])},
	}
}
