package main

import "fmt"

func evaluateSLO(result LoadResult, spec HTTPRequestSpec, cfg Config) SLOResult {
	maxP95 := firstPositive(spec.MaxP95MS, cfg.DefaultMaxP95MS)
	maxP99 := firstPositive(spec.MaxP99MS, cfg.DefaultMaxP99MS)
	minRPS := firstPositive(spec.MinRPS, cfg.DefaultMinRPS)
	thresholds := map[string]float64{
		"max_error_rate": cfg.MaxErrorRate,
		"max_p95_ms":     maxP95,
		"max_p99_ms":     maxP99,
		"min_rps":        minRPS,
	}
	observed := map[string]float64{
		"error_rate": result.ErrorRate,
		"p95_ms":     result.LatencyMs.P95,
		"p99_ms":     result.LatencyMs.P99,
		"rps":        result.RequestsPerSec,
	}
	failures := []string{}
	if result.ErrorRate > cfg.MaxErrorRate {
		failures = append(failures, fmt.Sprintf("error_rate %.6f > %.6f", result.ErrorRate, cfg.MaxErrorRate))
	}
	if result.LatencyMs.P95 > maxP95 {
		failures = append(failures, fmt.Sprintf("p95 %.4fms > %.4fms", result.LatencyMs.P95, maxP95))
	}
	if result.LatencyMs.P99 > maxP99 {
		failures = append(failures, fmt.Sprintf("p99 %.4fms > %.4fms", result.LatencyMs.P99, maxP99))
	}
	if result.RequestsPerSec < minRPS {
		failures = append(failures, fmt.Sprintf("rps %.2f < %.2f", result.RequestsPerSec, minRPS))
	}
	return SLOResult{
		Passed:     len(failures) == 0,
		Failures:   failures,
		Thresholds: thresholds,
		Observed:   observed,
	}
}

func firstPositive(values ...float64) float64 {
	for _, value := range values {
		if value > 0 {
			return value
		}
	}
	return 0
}
