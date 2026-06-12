package main

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func buildPerformanceBudgetReport(cfg Config, artifacts ArtifactSet) PerformanceBudgetReport {
	budgets := evaluateBudgets(cfg, artifacts)
	passed := true
	passedCount := 0
	byLanguage := map[string]int{}
	for _, budget := range budgets {
		byLanguage[budget.Language]++
		if budget.Passed {
			passedCount++
		} else {
			passed = false
		}
	}
	return PerformanceBudgetReport{
		SchemaVersion: "tryops.native_performance_budget.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		CoverageLevel: "native_ci_budget_rust_go_cpp",
		Summary: BudgetSummary{
			TotalBudgets:  len(budgets),
			PassedBudgets: passedCount,
			FailedBudgets: len(budgets) - passedCount,
			ByLanguage:    byLanguage,
		},
		Inputs:  artifacts.Inputs,
		Budgets: budgets,
		CI: CIContract{
			ArtifactName:    cfg.ArtifactName,
			JSONPath:        cfg.OutputPath,
			MarkdownPath:    cfg.MarkdownPath,
			StepSummaryPath: cfg.StepSummaryPath,
			Notes: []string{
				"Upload the JSON and Markdown outputs as CI artifacts.",
				"Append the Markdown output to GITHUB_STEP_SUMMARY for reviewable pull-request evidence.",
				"Run this gate after native benchmark, SLO, config-contract, and C++ perf artifacts are produced.",
			},
		},
	}
}

func evaluateBudgets(cfg Config, artifacts ArtifactSet) []BudgetResult {
	budgets := []BudgetResult{
		evaluateBenchmarkBudget(artifacts, benchmarkBudgetSpec{
			name:               "rust_gateway_health_latency",
			scenario:           "health_get",
			target:             "native_rust_gateway",
			compareTarget:      "python_fastapi",
			maxErrors:          0,
			maxP95MS:           20,
			maxP99MS:           35,
			minRPS:             10000,
			minThroughputRatio: 2,
		}),
		evaluateBenchmarkBudget(artifacts, benchmarkBudgetSpec{
			name:               "rust_gateway_promotion_direct_latency",
			scenario:           "promotion_post_direct",
			target:             "native_rust_gateway",
			compareTarget:      "python_fastapi",
			maxErrors:          0,
			maxP95MS:           20,
			maxP99MS:           35,
			minRPS:             10000,
			minThroughputRatio: 2,
		}),
		evaluateBenchmarkBudget(artifacts, benchmarkBudgetSpec{
			name:               "rust_edge_proxy_overhead",
			scenario:           "promotion_post_edge_proxy",
			target:             "native_rust_gateway_proxy_to_fastapi",
			compareTarget:      "python_fastapi_direct",
			maxErrors:          0,
			maxP95MS:           150,
			maxP99MS:           220,
			minRPS:             400,
			minThroughputRatio: 0.75,
			maxP95Ratio:        1.25,
			maxP99Ratio:        1.25,
		}),
		evaluateSLOGateBudget(artifacts),
		evaluateConfigContractBudget(artifacts),
		evaluatePerfStatsBudget(artifacts),
	}
	for _, binary := range nativeBinarySpecs() {
		budgets = append(budgets, evaluateBinaryBudget(cfg, binary))
	}
	return budgets
}

type benchmarkBudgetSpec struct {
	name               string
	scenario           string
	target             string
	compareTarget      string
	maxErrors          int
	maxP95MS           float64
	maxP99MS           float64
	minRPS             float64
	minThroughputRatio float64
	maxP95Ratio        float64
	maxP99Ratio        float64
}

func evaluateBenchmarkBudget(artifacts ArtifactSet, spec benchmarkBudgetSpec) BudgetResult {
	result := baseBudget(spec.name, "rust", "latency_throughput", inputByName(artifacts.Inputs, "gateway_benchmark").Path)
	result.Thresholds = map[string]float64{
		"max_errors":              float64(spec.maxErrors),
		"max_p95_ms":              spec.maxP95MS,
		"max_p99_ms":              spec.maxP99MS,
		"min_requests_per_second": spec.minRPS,
	}
	if spec.minThroughputRatio > 0 {
		result.Thresholds["min_throughput_ratio"] = spec.minThroughputRatio
	}
	if spec.maxP95Ratio > 0 {
		result.Thresholds["max_p95_ratio"] = spec.maxP95Ratio
	}
	if spec.maxP99Ratio > 0 {
		result.Thresholds["max_p99_ratio"] = spec.maxP99Ratio
	}
	if !inputByName(artifacts.Inputs, "gateway_benchmark").Present {
		return failBudget(result, "gateway benchmark artifact missing")
	}
	scenario, ok := artifacts.Benchmark.Scenarios[spec.scenario]
	if !ok {
		return failBudget(result, fmt.Sprintf("benchmark scenario %q missing", spec.scenario))
	}
	target, ok := scenario.Results[spec.target]
	if !ok {
		return failBudget(result, fmt.Sprintf("benchmark target %q missing", spec.target))
	}
	result.Evidence["scenario"] = spec.scenario
	result.Evidence["target"] = spec.target
	result.Evidence["endpoint"] = scenario.Endpoint
	result.Measurements["errors"] = float64(target.Errors)
	result.Measurements["p95_ms"] = target.LatencyMs.P95
	result.Measurements["p99_ms"] = target.LatencyMs.P99
	result.Measurements["requests_per_second"] = target.RequestsPerSec
	if target.Errors > spec.maxErrors {
		result = failBudget(result, fmt.Sprintf("errors %d > %d", target.Errors, spec.maxErrors))
	}
	if target.LatencyMs.P95 > spec.maxP95MS {
		result = failBudget(result, fmt.Sprintf("p95_ms %.3f > %.3f", target.LatencyMs.P95, spec.maxP95MS))
	}
	if target.LatencyMs.P99 > spec.maxP99MS {
		result = failBudget(result, fmt.Sprintf("p99_ms %.3f > %.3f", target.LatencyMs.P99, spec.maxP99MS))
	}
	if target.RequestsPerSec < spec.minRPS {
		result = failBudget(result, fmt.Sprintf("requests_per_second %.3f < %.3f", target.RequestsPerSec, spec.minRPS))
	}
	if spec.compareTarget != "" {
		compare, ok := scenario.Results[spec.compareTarget]
		if !ok {
			return failBudget(result, fmt.Sprintf("benchmark comparison target %q missing", spec.compareTarget))
		}
		throughputRatio := ratio(target.RequestsPerSec, compare.RequestsPerSec)
		p95Ratio := ratio(target.LatencyMs.P95, compare.LatencyMs.P95)
		p99Ratio := ratio(target.LatencyMs.P99, compare.LatencyMs.P99)
		result.Evidence["compare_target"] = spec.compareTarget
		result.Measurements["throughput_ratio"] = throughputRatio
		result.Measurements["p95_ratio"] = p95Ratio
		result.Measurements["p99_ratio"] = p99Ratio
		if spec.minThroughputRatio > 0 && throughputRatio < spec.minThroughputRatio {
			result = failBudget(result, fmt.Sprintf("throughput_ratio %.3f < %.3f", throughputRatio, spec.minThroughputRatio))
		}
		if spec.maxP95Ratio > 0 && p95Ratio > spec.maxP95Ratio {
			result = failBudget(result, fmt.Sprintf("p95_ratio %.3f > %.3f", p95Ratio, spec.maxP95Ratio))
		}
		if spec.maxP99Ratio > 0 && p99Ratio > spec.maxP99Ratio {
			result = failBudget(result, fmt.Sprintf("p99_ratio %.3f > %.3f", p99Ratio, spec.maxP99Ratio))
		}
	}
	return result
}

func evaluateSLOGateBudget(artifacts ArtifactSet) BudgetResult {
	result := baseBudget("go_slo_regression_gate", "go", "ci_gate", inputByName(artifacts.Inputs, "slo_gate").Path)
	result.Thresholds = map[string]float64{"min_total_rules": 3, "max_failed_rules": 0}
	if !inputByName(artifacts.Inputs, "slo_gate").Present {
		return failBudget(result, "SLO gate artifact missing")
	}
	result.Measurements["passed"] = boolAsFloat(artifacts.SLOGate.Passed)
	result.Measurements["total_rules"] = float64(artifacts.SLOGate.Summary.TotalRules)
	result.Measurements["failed_rules"] = float64(artifacts.SLOGate.Summary.FailedRules)
	if !artifacts.SLOGate.Passed {
		result = failBudget(result, "SLO gate report did not pass")
	}
	if artifacts.SLOGate.Summary.TotalRules < 3 {
		result = failBudget(result, fmt.Sprintf("total_rules %d < 3", artifacts.SLOGate.Summary.TotalRules))
	}
	if artifacts.SLOGate.Summary.FailedRules > 0 {
		result = failBudget(result, fmt.Sprintf("failed_rules %d > 0", artifacts.SLOGate.Summary.FailedRules))
	}
	return result
}

func evaluateConfigContractBudget(artifacts ArtifactSet) BudgetResult {
	result := baseBudget("go_config_contract_drift_gate", "go", "config_contract", inputByName(artifacts.Inputs, "config_contract").Path)
	result.Thresholds = map[string]float64{"min_services": 9, "min_checks": 60, "max_failed_checks": 0}
	if !inputByName(artifacts.Inputs, "config_contract").Present {
		return failBudget(result, "config contract artifact missing")
	}
	failedChecks := 0
	for _, check := range artifacts.ConfigContract.Checks {
		if !check.Passed {
			failedChecks++
		}
	}
	result.Evidence["coverage_level"] = artifacts.ConfigContract.CoverageLevel
	result.Measurements["passed"] = boolAsFloat(artifacts.ConfigContract.Passed)
	result.Measurements["services"] = float64(len(artifacts.ConfigContract.Services))
	result.Measurements["checks"] = float64(len(artifacts.ConfigContract.Checks))
	result.Measurements["failed_checks"] = float64(failedChecks)
	if !artifacts.ConfigContract.Passed {
		result = failBudget(result, "config contract report did not pass")
	}
	if len(artifacts.ConfigContract.Services) < 9 {
		result = failBudget(result, fmt.Sprintf("services %d < 9", len(artifacts.ConfigContract.Services)))
	}
	if len(artifacts.ConfigContract.Checks) < 60 {
		result = failBudget(result, fmt.Sprintf("checks %d < 60", len(artifacts.ConfigContract.Checks)))
	}
	if failedChecks > 0 {
		result = failBudget(result, fmt.Sprintf("failed_checks %d > 0", failedChecks))
	}
	return result
}

func evaluatePerfStatsBudget(artifacts ArtifactSet) BudgetResult {
	result := baseBudget("cpp_perf_stats_slo", "cpp", "llm_perf", inputByName(artifacts.Inputs, "perf_stats").Path)
	result.Thresholds = map[string]float64{"max_return_code": 0, "max_p95_ms": 100, "min_tokens_per_second_mean": 5, "min_sample_count": 3}
	if !inputByName(artifacts.Inputs, "perf_stats").Present {
		return failBudget(result, "C++ perf stats artifact missing")
	}
	nativeStats := artifacts.PerfStats.NativeStats
	result.Evidence["cli_path"] = nativeStats.CLIPath
	result.Evidence["slo_verdict"] = nativeStats.SLO.Verdict
	result.Measurements["available"] = boolAsFloat(nativeStats.Available)
	result.Measurements["return_code"] = float64(nativeStats.ReturnCode)
	result.Measurements["sample_count"] = float64(artifacts.PerfStats.SampleCount)
	result.Measurements["p95_ms"] = nativeStats.LatencyMs.P95
	result.Measurements["tokens_per_second_mean"] = nativeStats.TokensPerSecond.Mean
	if !nativeStats.Available {
		result = failBudget(result, "native C++ stats unavailable")
	}
	if nativeStats.ReturnCode != 0 {
		result = failBudget(result, fmt.Sprintf("return_code %d != 0", nativeStats.ReturnCode))
	}
	if artifacts.PerfStats.SampleCount < 3 {
		result = failBudget(result, fmt.Sprintf("sample_count %d < 3", artifacts.PerfStats.SampleCount))
	}
	if nativeStats.LatencyMs.P95 > 100 {
		result = failBudget(result, fmt.Sprintf("p95_ms %.3f > 100.000", nativeStats.LatencyMs.P95))
	}
	if nativeStats.TokensPerSecond.Mean < 5 {
		result = failBudget(result, fmt.Sprintf("tokens_per_second_mean %.3f < 5.000", nativeStats.TokensPerSecond.Mean))
	}
	if nativeStats.SLO.Verdict != "pass" {
		result = failBudget(result, fmt.Sprintf("slo_verdict %q != pass", nativeStats.SLO.Verdict))
	}
	return result
}

type nativeBinarySpec struct {
	name     string
	language string
	path     string
}

func nativeBinarySpecs() []nativeBinarySpec {
	return []nativeBinarySpec{
		{name: "rust_gateway_binary", language: "rust", path: "artifacts/native/tryops-gateway"},
		{name: "go_benchmark_binary", language: "go", path: "artifacts/native/tryops_benchmark"},
		{name: "go_slo_gate_binary", language: "go", path: "artifacts/native/tryops_slo_gate"},
		{name: "go_config_contract_binary", language: "go", path: "artifacts/native/tryops_config_contract"},
		{name: "cpp_perf_stats_binary", language: "cpp", path: "artifacts/native/tryops_perf_stats_cli"},
	}
}

func evaluateBinaryBudget(cfg Config, spec nativeBinarySpec) BudgetResult {
	result := baseBudget(spec.name, spec.language, "binary_artifact", spec.path)
	result.Thresholds = map[string]float64{"min_size_bytes": 1, "required_executable": 1}
	fullPath := resolvePath(cfg.Root, spec.path)
	info, err := os.Stat(fullPath)
	if err != nil {
		if os.IsNotExist(err) {
			return failBudget(result, "native binary missing")
		}
		return failBudget(result, err.Error())
	}
	result.Measurements["size_bytes"] = float64(info.Size())
	if info.Size() <= 0 {
		result = failBudget(result, "native binary is empty")
	}
	executable := info.Mode().Perm()&0o111 != 0
	result.Measurements["executable"] = boolAsFloat(executable)
	if !executable {
		result = failBudget(result, "native binary is not executable")
	}
	result.Evidence["path"] = filepath.Clean(spec.path)
	return result
}

func baseBudget(name string, language string, category string, sourceArtifact string) BudgetResult {
	return BudgetResult{
		Name:           name,
		Language:       language,
		Category:       category,
		SourceArtifact: sourceArtifact,
		Passed:         true,
		Measurements:   map[string]float64{},
		Thresholds:     map[string]float64{},
		Evidence:       map[string]string{},
	}
}

func failBudget(result BudgetResult, message string) BudgetResult {
	result.Passed = false
	result.Failures = append(result.Failures, message)
	return result
}

func ratio(left float64, right float64) float64 {
	if right == 0 {
		return 0
	}
	return left / right
}

func boolAsFloat(value bool) float64 {
	if value {
		return 1
	}
	return 0
}
