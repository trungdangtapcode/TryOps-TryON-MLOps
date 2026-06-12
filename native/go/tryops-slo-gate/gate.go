package main

import (
	"fmt"
)

func evaluateGate(report BenchmarkReport, policy GatePolicy) []RuleResult {
	results := make([]RuleResult, 0, len(policy.Rules))
	for _, rule := range policy.Rules {
		results = append(results, evaluateRule(report, rule))
	}
	return results
}

func evaluateRule(report BenchmarkReport, rule ScenarioPolicy) RuleResult {
	result := RuleResult{
		Name:         rule.Name,
		Scenario:     rule.Scenario,
		Target:       rule.Target,
		Passed:       true,
		Measurements: map[string]float64{},
		Thresholds:   thresholds(rule),
	}
	scenario, ok := report.Scenarios[rule.Scenario]
	if !ok {
		return fail(result, fmt.Sprintf("scenario %q missing", rule.Scenario))
	}
	result.Endpoint = scenario.Endpoint
	load, ok := scenario.Results[rule.Target]
	if !ok {
		return fail(result, fmt.Sprintf("target %q missing from scenario %q", rule.Target, rule.Scenario))
	}

	errorRate := 0.0
	if load.Requests > 0 {
		errorRate = float64(load.Errors) / float64(load.Requests)
	}
	result.Measurements["errors"] = float64(load.Errors)
	result.Measurements["error_rate"] = errorRate
	result.Measurements["p95_ms"] = load.LatencyMs.P95
	result.Measurements["p99_ms"] = load.LatencyMs.P99
	result.Measurements["requests_per_second"] = load.RequestsPerSec

	if load.Errors > rule.MaxErrors {
		result = fail(result, fmt.Sprintf("errors %d > %d", load.Errors, rule.MaxErrors))
	}
	if errorRate > rule.MaxErrorRate {
		result = fail(result, fmt.Sprintf("error_rate %.6f > %.6f", errorRate, rule.MaxErrorRate))
	}
	if rule.MaxP95MS > 0 && load.LatencyMs.P95 > rule.MaxP95MS {
		result = fail(result, fmt.Sprintf("p95_ms %.3f > %.3f", load.LatencyMs.P95, rule.MaxP95MS))
	}
	if rule.MaxP99MS > 0 && load.LatencyMs.P99 > rule.MaxP99MS {
		result = fail(result, fmt.Sprintf("p99_ms %.3f > %.3f", load.LatencyMs.P99, rule.MaxP99MS))
	}
	if rule.MinRequestsPerSecond > 0 && load.RequestsPerSec < rule.MinRequestsPerSecond {
		result = fail(result, fmt.Sprintf("requests_per_second %.3f < %.3f", load.RequestsPerSec, rule.MinRequestsPerSecond))
	}

	if rule.CompareTarget != "" {
		compare, ok := scenario.Results[rule.CompareTarget]
		if !ok {
			return fail(result, fmt.Sprintf("comparison target %q missing from scenario %q", rule.CompareTarget, rule.Scenario))
		}
		addComparisonMeasurements(&result, load, compare)
		if rule.MinThroughputRatio > 0 && ratio(load.RequestsPerSec, compare.RequestsPerSec) < rule.MinThroughputRatio {
			result = fail(result, fmt.Sprintf("throughput_ratio %.3f < %.3f", ratio(load.RequestsPerSec, compare.RequestsPerSec), rule.MinThroughputRatio))
		}
		if rule.MaxP95Ratio > 0 && ratio(load.LatencyMs.P95, compare.LatencyMs.P95) > rule.MaxP95Ratio {
			result = fail(result, fmt.Sprintf("p95_ratio %.3f > %.3f", ratio(load.LatencyMs.P95, compare.LatencyMs.P95), rule.MaxP95Ratio))
		}
		if rule.MaxP99Ratio > 0 && ratio(load.LatencyMs.P99, compare.LatencyMs.P99) > rule.MaxP99Ratio {
			result = fail(result, fmt.Sprintf("p99_ratio %.3f > %.3f", ratio(load.LatencyMs.P99, compare.LatencyMs.P99), rule.MaxP99Ratio))
		}
		if rule.RequiredSpeedup != nil && ratio(load.RequestsPerSec, compare.RequestsPerSec) < *rule.RequiredSpeedup {
			result = fail(result, fmt.Sprintf("speedup %.3f < %.3f", ratio(load.RequestsPerSec, compare.RequestsPerSec), *rule.RequiredSpeedup))
		}
	}

	return result
}

func addComparisonMeasurements(result *RuleResult, target LoadResult, compare LoadResult) {
	result.Measurements["throughput_ratio"] = ratio(target.RequestsPerSec, compare.RequestsPerSec)
	result.Measurements["p95_ratio"] = ratio(target.LatencyMs.P95, compare.LatencyMs.P95)
	result.Measurements["p99_ratio"] = ratio(target.LatencyMs.P99, compare.LatencyMs.P99)
}

func thresholds(rule ScenarioPolicy) map[string]float64 {
	out := map[string]float64{
		"max_errors":              float64(rule.MaxErrors),
		"max_error_rate":          rule.MaxErrorRate,
		"max_p95_ms":              rule.MaxP95MS,
		"max_p99_ms":              rule.MaxP99MS,
		"min_requests_per_second": rule.MinRequestsPerSecond,
		"min_throughput_ratio":    rule.MinThroughputRatio,
		"max_p95_ratio":           rule.MaxP95Ratio,
		"max_p99_ratio":           rule.MaxP99Ratio,
	}
	if rule.RequiredSpeedup != nil {
		out["required_speedup"] = *rule.RequiredSpeedup
	}
	return out
}

func fail(result RuleResult, message string) RuleResult {
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
