package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPerformanceBudgetPassesCompleteFixture(t *testing.T) {
	root := completeFixture(t)
	cfg := testConfig(root)
	artifacts, err := loadArtifacts(cfg)
	if err != nil {
		t.Fatal(err)
	}
	report := buildPerformanceBudgetReport(cfg, artifacts)
	if !report.Passed {
		t.Fatalf("expected pass, got failures: %#v", failedBudgets(report.Budgets))
	}
	if report.Summary.TotalBudgets != 11 {
		t.Fatalf("unexpected budget count: %d", report.Summary.TotalBudgets)
	}
	if report.Summary.ByLanguage["rust"] == 0 || report.Summary.ByLanguage["go"] == 0 || report.Summary.ByLanguage["cpp"] == 0 {
		t.Fatalf("expected rust/go/cpp coverage: %#v", report.Summary.ByLanguage)
	}
}

func TestPerformanceBudgetFailsMissingArtifacts(t *testing.T) {
	root := t.TempDir()
	cfg := testConfig(root)
	artifacts, err := loadArtifacts(cfg)
	if err != nil {
		t.Fatal(err)
	}
	report := buildPerformanceBudgetReport(cfg, artifacts)
	if report.Passed {
		t.Fatal("expected failure when artifacts are missing")
	}
	if len(failedBudgets(report.Budgets)) == 0 {
		t.Fatal("expected failed budget rows")
	}
}

func TestPerformanceBudgetFailsLatencyRegression(t *testing.T) {
	root := completeFixture(t)
	benchmarkPath := filepath.Join(root, "artifacts", "eval", "gateway_benchmark", "native_gateway_benchmark.json")
	payload, err := os.ReadFile(benchmarkPath)
	if err != nil {
		t.Fatal(err)
	}
	regressed := strings.Replace(string(payload), `"p95":6.0`, `"p95":60.0`, 1)
	if err := os.WriteFile(benchmarkPath, []byte(regressed), 0o644); err != nil {
		t.Fatal(err)
	}
	cfg := testConfig(root)
	artifacts, err := loadArtifacts(cfg)
	if err != nil {
		t.Fatal(err)
	}
	report := buildPerformanceBudgetReport(cfg, artifacts)
	if report.Passed {
		t.Fatal("expected latency regression failure")
	}
	var found bool
	for _, budget := range failedBudgets(report.Budgets) {
		if budget.Name == "rust_gateway_health_latency" {
			found = true
		}
	}
	if !found {
		t.Fatalf("expected health latency budget failure: %#v", failedBudgets(report.Budgets))
	}
}

func TestRenderMarkdownIncludesFailures(t *testing.T) {
	root := t.TempDir()
	cfg := testConfig(root)
	artifacts, err := loadArtifacts(cfg)
	if err != nil {
		t.Fatal(err)
	}
	report := buildPerformanceBudgetReport(cfg, artifacts)
	markdown := renderMarkdown(report)
	if !strings.Contains(markdown, "Native Performance Budget: FAIL") || !strings.Contains(markdown, "## Failures") {
		t.Fatalf("unexpected markdown:\n%s", markdown)
	}
}

func completeFixture(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	writeTestJSON(t, filepath.Join(root, "artifacts", "eval", "gateway_benchmark", "native_gateway_benchmark.json"), `{
		"schema_version":"tryops.native_gateway_benchmark.v1",
		"created_at":"2026-06-12T00:00:00Z",
		"load":{"requests":12000,"concurrency":50},
		"scenarios":{
			"health_get":{"endpoint":"/health","results":{
				"native_rust_gateway":{"requests":12000,"errors":0,"requests_per_sec":20000,"latency_ms":{"p95":6.0,"p99":10.0}},
				"python_fastapi":{"requests":12000,"errors":0,"requests_per_sec":1000,"latency_ms":{"p95":60.0,"p99":80.0}}
			}},
			"promotion_post_direct":{"endpoint":"/v1/promotion/evaluate","results":{
				"native_rust_gateway":{"requests":12000,"errors":0,"requests_per_sec":18000,"latency_ms":{"p95":7.0,"p99":12.0}},
				"python_fastapi":{"requests":12000,"errors":0,"requests_per_sec":800,"latency_ms":{"p95":90.0,"p99":120.0}}
			}},
			"promotion_post_edge_proxy":{"endpoint":"/api/promotion/evaluate -> /v1/promotion/evaluate","results":{
				"native_rust_gateway_proxy_to_fastapi":{"requests":12000,"errors":0,"requests_per_sec":700,"latency_ms":{"p95":105.0,"p99":130.0}},
				"python_fastapi_direct":{"requests":12000,"errors":0,"requests_per_sec":760,"latency_ms":{"p95":96.0,"p99":120.0}}
			}}
		}
	}`)
	writeTestJSON(t, filepath.Join(root, "artifacts", "eval", "slo", "native_slo_gate_report.json"), `{
		"schema_version":"tryops.native_slo_gate.v1",
		"generated_at":"2026-06-12T00:00:00Z",
		"passed":true,
		"summary":{"total_rules":3,"passed_rules":3,"failed_rules":0}
	}`)
	writeTestJSON(t, filepath.Join(root, "artifacts", "eval", "perf_stats", "perf_stats.json"), `{
		"schema_version":"tryops.native_perf_stats.report.v1",
		"created_at":"2026-06-12T00:00:00Z",
		"sample_count":3,
		"native_stats":{
			"available":true,
			"cli_path":"artifacts/native/tryops_perf_stats_cli",
			"returncode":0,
			"latency_ms":{"p95":0.026},
			"tokens_per_second":{"mean":40000},
			"slo":{"verdict":"pass"}
		}
	}`)
	writeTestJSON(t, filepath.Join(root, "artifacts", "eval", "config", "native_config_contract_report.json"), `{
		"schema_version":"tryops.native_config_contract.v1",
		"generated_at":"2026-06-12T00:00:00Z",
		"passed":true,
		"coverage_level":"native_compose_env_healthcheck_contract",
		"services":[{"name":"api"},{"name":"gateway"},{"name":"postgres"},{"name":"valkey"},{"name":"minio"},{"name":"mlflow"},{"name":"prometheus"},{"name":"grafana"},{"name":"guardrail"}],
		"checks":[
			{"name":"c01","passed":true},{"name":"c02","passed":true},{"name":"c03","passed":true},{"name":"c04","passed":true},{"name":"c05","passed":true},
			{"name":"c06","passed":true},{"name":"c07","passed":true},{"name":"c08","passed":true},{"name":"c09","passed":true},{"name":"c10","passed":true},
			{"name":"c11","passed":true},{"name":"c12","passed":true},{"name":"c13","passed":true},{"name":"c14","passed":true},{"name":"c15","passed":true},
			{"name":"c16","passed":true},{"name":"c17","passed":true},{"name":"c18","passed":true},{"name":"c19","passed":true},{"name":"c20","passed":true},
			{"name":"c21","passed":true},{"name":"c22","passed":true},{"name":"c23","passed":true},{"name":"c24","passed":true},{"name":"c25","passed":true},
			{"name":"c26","passed":true},{"name":"c27","passed":true},{"name":"c28","passed":true},{"name":"c29","passed":true},{"name":"c30","passed":true},
			{"name":"c31","passed":true},{"name":"c32","passed":true},{"name":"c33","passed":true},{"name":"c34","passed":true},{"name":"c35","passed":true},
			{"name":"c36","passed":true},{"name":"c37","passed":true},{"name":"c38","passed":true},{"name":"c39","passed":true},{"name":"c40","passed":true},
			{"name":"c41","passed":true},{"name":"c42","passed":true},{"name":"c43","passed":true},{"name":"c44","passed":true},{"name":"c45","passed":true},
			{"name":"c46","passed":true},{"name":"c47","passed":true},{"name":"c48","passed":true},{"name":"c49","passed":true},{"name":"c50","passed":true},
			{"name":"c51","passed":true},{"name":"c52","passed":true},{"name":"c53","passed":true},{"name":"c54","passed":true},{"name":"c55","passed":true},
			{"name":"c56","passed":true},{"name":"c57","passed":true},{"name":"c58","passed":true},{"name":"c59","passed":true},{"name":"c60","passed":true}
		]
	}`)
	for _, binary := range nativeBinarySpecs() {
		path := filepath.Join(root, binary.path)
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte("binary"), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	return root
}

func testConfig(root string) Config {
	return Config{
		Root:               root,
		BenchmarkPath:      "artifacts/eval/gateway_benchmark/native_gateway_benchmark.json",
		SLOGatePath:        "artifacts/eval/slo/native_slo_gate_report.json",
		PerfStatsPath:      "artifacts/eval/perf_stats/perf_stats.json",
		ConfigContractPath: "artifacts/eval/config/native_config_contract_report.json",
		OutputPath:         "artifacts/eval/performance/native_performance_budget.json",
		MarkdownPath:       "artifacts/eval/performance/native_performance_budget.md",
		ArtifactName:       "tryops-native-performance-budget",
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
