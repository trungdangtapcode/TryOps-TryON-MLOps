package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

func buildIndex(root string) (evaluationIndex, error) {
	paths, err := discoverJSONReports(root)
	if err != nil {
		return evaluationIndex{}, err
	}
	reports := make([]artifactReport, 0, len(paths))
	for _, path := range paths {
		data, err := readJSON(path)
		if err != nil {
			continue
		}
		reports = append(reports, buildReport(root, path, data))
	}
	pipelineRuns := buildPipelineRuns(root)
	sort.Slice(reports, func(i int, j int) bool {
		if reports[i].Category == reports[j].Category {
			return reports[i].Path < reports[j].Path
		}
		return reports[i].Category < reports[j].Category
	})
	return evaluationIndex{
		SchemaVersion: "tryops.evaluation_index.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		SourceRoots:   []string{"artifacts/eval", "reports/generated"},
		TotalReports:  len(reports),
		StatusCounts:  countByStatus(reports),
		CategoryCount: countByCategory(reports),
		Highlights:    selectHighlights(reports),
		Optimization:  buildOptimizationPanel(root),
		PipelineRuns:  pipelineRuns,
		Reports:       reports,
	}, nil
}

func countByStatus(reports []artifactReport) map[string]int {
	counts := map[string]int{}
	for _, report := range reports {
		counts[report.Status]++
	}
	return counts
}

func countByCategory(reports []artifactReport) map[string]int {
	counts := map[string]int{}
	for _, report := range reports {
		counts[report.Category]++
	}
	return counts
}

func selectHighlights(reports []artifactReport) map[string]artifactReport {
	targets := map[string]struct {
		schema       string
		preferredSub string
	}{
		"llm_pareto":         {schema: "tryops.llm_pareto.v1", preferredSub: "llm_pareto/pareto.json"},
		"llm_quantized":      {schema: "tryops.quantized_model_preflight.v1", preferredSub: "llm_quantized/quantized_model_preflight.json"},
		"llm_gguf":           {schema: "tryops.native_gguf_preflight.v1", preferredSub: "llm_gguf/gguf_preflight.json"},
		"llm_vllm":           {schema: "tryops.vllm_serving_probe.v1", preferredSub: "llm_vllm/vllm_serving_probe.json"},
		"energy":             {schema: "tryops.energy_report.v1", preferredSub: "energy/energy_sweep.json"},
		"vton_comparison":    {schema: "tryops.vton_comparison.v1", preferredSub: "vton_comparison/comparison.json"},
		"vton_clip":          {schema: "tryops.garment_similarity.v1", preferredSub: "vton_clip/garment_clip_similarity.json"},
		"vton_native_api":    {schema: "tryops.vton_native_api.v1", preferredSub: "vton_native_api/vton_native_api_report.json"},
		"drift":              {schema: "tryops.drift_summary.v1", preferredSub: "drift/drift_summary.json"},
		"full_stack":         {schema: "tryops.full_stack_smoke.v1", preferredSub: "full_stack/full_stack_smoke.json"},
		"demo_acceptance":    {schema: "tryops.professor_demo_acceptance.v1", preferredSub: "demo_acceptance/professor_demo_acceptance.json"},
		"demo_video":         {schema: "tryops.professor_demo_video.v1", preferredSub: "demo_video/professor_demo_video.json"},
		"vulnerability":      {schema: "tryops.vulnerability_scan.v1", preferredSub: "security/vulnerability_scan_report.json"},
		"ci_contract":        {schema: "tryops.native_ci_contract.v1", preferredSub: "ci/native_ci_contract.json"},
		"dependency_lock":    {schema: "tryops.native_dependency_lock_contract.v1", preferredSub: "dependencies/native_dependency_lock_contract.json"},
		"data_versioning":    {schema: "tryops.dvc_minio_versioning.v1", preferredSub: "data_versioning/dvc_minio_report.json"},
		"config_contract":    {schema: "tryops.native_config_contract.v1", preferredSub: "config/native_config_contract_report.json"},
		"postgres_migration": {schema: "tryops.native_postgres_migration.v1", preferredSub: "postgres/native_postgres_migration_live.json"},
		"backup_restore":     {schema: "tryops.native_backup_restore_drill.v1", preferredSub: "backup/native_backup_restore_live.json"},
		"tls_contract":       {schema: "tryops.native_tls_contract.v1", preferredSub: "tls/native_tls_contract_live.json"},
		"secret_rotation":    {schema: "tryops.native_secret_rotation_contract.v1", preferredSub: "secrets/native_secret_rotation_contract.json"},
		"fullstack_load":     {schema: "tryops.native_fullstack_load.v1", preferredSub: "load/native_fullstack_load.json"},
		"container_contract": {schema: "tryops.native_container_contract.v1", preferredSub: "containers/native_container_contract_report.json"},
		"distributed_quota":  {schema: "tryops.distributed_quota_admission.v1", preferredSub: "quota/native_distributed_quota_admission.json"},
		"quota_read_model":   {schema: "tryops.native_quota_read_model.v1", preferredSub: "quota/native_quota_read_model.json"},
		"runtime_telemetry":  {schema: "tryops.native_runtime_telemetry.v1", preferredSub: "runtime/native_runtime_telemetry.json"},
		"trace_envelope":     {schema: "tryops.native_trace_envelope.v1", preferredSub: "trace_envelope/native_trace_envelope_report.json"},
		"observability":      {schema: "tryops.native_observability_contract.v1", preferredSub: "observability/native_observability_contract.json"},
		"alertmanager":       {schema: "tryops.native_alertmanager_contract.v1", preferredSub: "alerts/native_alertmanager_contract.json"},
		"incident_workflow":  {schema: "tryops.native_incident_workflow.v1", preferredSub: "incidents/native_incident_workflow.json"},
		"performance_budget": {schema: "tryops.native_performance_budget.v1", preferredSub: "performance/native_performance_budget.json"},
	}
	highlights := map[string]artifactReport{}
	for key, target := range targets {
		for _, report := range reports {
			if report.SchemaVersion == target.schema && strings.Contains(report.Path, target.preferredSub) {
				highlights[key] = report
				break
			}
		}
		if _, ok := highlights[key]; ok {
			continue
		}
		for _, report := range reports {
			if report.SchemaVersion == target.schema {
				highlights[key] = report
				break
			}
		}
	}
	return highlights
}

func writeIndex(path string, index evaluationIndex) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(index, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}
