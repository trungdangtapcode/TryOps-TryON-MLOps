package main

import "testing"

func TestValidateLLMParetoRequiresPassingRecommendation(t *testing.T) {
	data := map[string]interface{}{
		"schema_version":  "tryops.llm_pareto.v1",
		"pareto_frontier": []interface{}{"4bit"},
		"recommendation":  map[string]interface{}{"variant": "4bit"},
		"variants": []interface{}{
			map[string]interface{}{
				"variant": "4bit",
				"slo":     map[string]interface{}{"verdict": "pass"},
			},
			map[string]interface{}{
				"variant": "8bit",
				"slo":     map[string]interface{}{"verdict": "fail"},
			},
		},
	}
	if failures := validateLLMPareto("", "", data); len(failures) != 0 {
		t.Fatalf("unexpected failures: %#v", failures)
	}
}

func TestValidateFullStackSmokeRequiresServiceChecks(t *testing.T) {
	data := map[string]interface{}{
		"schema_version": "tryops.full_stack_smoke.v1",
		"passed":         true,
		"checks": []interface{}{
			map[string]interface{}{"name": "gateway_console", "passed": true},
			map[string]interface{}{"name": "gateway_spa_fallback", "passed": true},
			map[string]interface{}{"name": "llm_generation_through_gateway", "passed": true},
			map[string]interface{}{"name": "gateway_metrics", "passed": true},
			map[string]interface{}{"name": "minio_ready", "passed": true},
			map[string]interface{}{"name": "mlflow_health", "passed": true},
		},
	}
	if failures := validateFullStackSmoke("", "", data); len(failures) != 0 {
		t.Fatalf("unexpected failures: %#v", failures)
	}
}

func TestValidateNativeQuotaLedgerRequiresRemainingCapacity(t *testing.T) {
	data := map[string]interface{}{
		"schema_version": "tryops.native_quota_batch.v1",
		"available":      true,
		"decisions": []interface{}{
			map[string]interface{}{
				"allowed": true,
				"checks": []interface{}{
					map[string]interface{}{
						"limit":           float64(20),
						"remaining_after": float64(18),
					},
				},
			},
		},
		"snapshot": map[string]interface{}{
			"usage": []interface{}{
				map[string]interface{}{"dimension": "llm_requests_per_day", "used": float64(2)},
			},
		},
	}
	if failures := validateNativeQuotaLedger("", "", data); len(failures) != 0 {
		t.Fatalf("unexpected failures: %#v", failures)
	}
}
