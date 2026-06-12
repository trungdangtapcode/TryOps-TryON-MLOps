package main

import "net/http"

func buildChecks(cfg config) []smokeCheck {
	llmPayload := `{"prompt":"Explain TryOps full-stack startup in one sentence.","model_alias":"baseline","max_tokens":64,"structured":true,"routing_mode":"direct","canary_percent":0,"shadow":false,"optimized_available":false,"fallback_enabled":true,"semantic_cache_enabled":true,"user_id":"stack-smoke","quota_plan":"free"}`
	badCandidatePayload := `{"request_id":"req-stack-block-demo","api_key":"tryops-risk-demo-key","target_stage":"champion","candidate":{"candidate_id":"vton-catvton-2026-06-11-bad","workload":"vton","model_name":"catvton-baseline","model_version":"0.1.1","metrics":{"garment_fidelity":0.61,"identity_preservation":0.65,"artifact_rate":0.21,"latency_p95_ms":18100},"artifacts":{"model_card":"s3://tryops-artifacts/model-cards/vton-catvton-bad.md","evaluation_report":"s3://tryops-artifacts/reports/vton-catvton-bad.json"},"approvals":["mlops_owner"],"risk_status":"unreviewed","vulnerabilities":{"critical":1,"high":2},"signed":false,"metadata":{"code_version":"local-dev","dataset_version":"vitonhd-demo-v1","pipeline_run_id":"run-vton-bad"}}}`
	return []smokeCheck{
		{
			Name:         "gateway_console",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/",
			WantStatus:   http.StatusOK,
			WantContains: []string{"TryOps Console", `<div id="root"></div>`},
		},
		{
			Name:         "gateway_spa_fallback",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/console/history",
			WantStatus:   http.StatusOK,
			WantContains: []string{"TryOps Console", `<div id="root"></div>`},
		},
		{
			Name:         "api_health_through_gateway",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/api/health",
			WantStatus:   http.StatusOK,
			WantContains: []string{`"status":"ok"`},
		},
		{
			Name:         "api_ready_through_gateway",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/api/ready",
			WantStatus:   http.StatusOK,
			WantContains: []string{`"status":"ready"`, `"rust_gateway"`},
		},
		{
			Name:         "llm_generation_through_gateway",
			Method:       http.MethodPost,
			URL:          cfg.GatewayURL + "/api/llm/generate",
			Body:         llmPayload,
			ContentType:  "application/json",
			WantStatus:   http.StatusOK,
			WantContains: []string{`"status":"completed"`, `"quota"`, `"trace"`, `"tryops.llm_generation.v1"`},
		},
		{
			Name:         "evaluation_summary_through_gateway",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/api/evaluations/summary?api_key=tryops-viewer-demo-key",
			WantStatus:   http.StatusOK,
			WantContains: []string{`"status":"ok"`, `"tryops.evaluation_index.v1"`, `"pipeline_runs"`, `"run-vton-001"`, `"COMPLETE"`, `"optimization_panel"`, `"recommended_variant":"4bit"`, `"carbon_gate_verdict":"pass"`, `"llm_pareto"`, `"energy"`},
		},
		{
			Name:         "gateway_auth_preflight_rejects_missing_key",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/api/evaluations/summary",
			WantStatus:   http.StatusUnauthorized,
			WantContains: []string{`auth_preflight_failed`, `admin:read`, `missing_api_key`},
		},
		{
			Name:         "gateway_auth_preflight_rejects_missing_scope",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/api/evaluations/summary?api_key=tryops-risk-demo-key",
			WantStatus:   http.StatusForbidden,
			WantContains: []string{`auth_preflight_failed`, `admin:read`, `missing_scope`},
		},
		{
			Name:         "vton_comparison_through_gateway",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/api/vton/comparison?api_key=tryops-viewer-demo-key",
			WantStatus:   http.StatusOK,
			WantContains: []string{`"status":"ok"`, `"tryops.vton_comparison.v1"`, `"output_url"`},
		},
		{
			Name:         "vton_artifact_image_through_gateway",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/api/artifacts/file?path=artifacts/eval/vton_comparison/naive_standard.png&api_key=tryops-viewer-demo-key",
			WantStatus:   http.StatusOK,
			WantContains: []string{},
		},
		{
			Name:        "bad_candidate_gate_through_gateway",
			Method:      http.MethodPost,
			URL:         cfg.GatewayURL + "/api/promotion/evaluate",
			Body:        badCandidatePayload,
			ContentType: "application/json",
			Headers: map[string]string{
				"x-tryops-artifact-signed": "true",
			},
			WantStatus: http.StatusOK,
			WantContains: []string{
				`"approved":false`,
				`"candidate artifact is not signed"`,
				`"critical vulnerabilities 1 > 0`,
				`"role":"risk_reviewer"`,
			},
		},
		{
			Name:       "rollback_state_artifact_through_gateway",
			Method:     http.MethodGet,
			URL:        cfg.GatewayURL + "/api/artifacts/file?path=artifacts/deployments/rollback_state.json&api_key=tryops-viewer-demo-key",
			WantStatus: http.StatusOK,
			WantContains: []string{
				`tryops.rollback_state.v1`,
				`tryops.rollback_record.v1`,
				`vton-catvton-previous`,
			},
		},
		{
			Name:         "gateway_metrics",
			Method:       http.MethodGet,
			URL:          cfg.GatewayURL + "/metrics",
			WantStatus:   http.StatusOK,
			WantContains: []string{"tryops_gateway_requests_total", "tryops_gateway_request_latency_ms_bucket", "tryops_gateway_auth_decisions_total"},
		},
		{
			Name:         "guardrail_health",
			Method:       http.MethodGet,
			URL:          cfg.GuardrailURL + "/health",
			WantStatus:   http.StatusOK,
			WantContains: []string{`"service":"tryops-guardrail"`, `"status":"ok"`},
		},
		{
			Name:         "prometheus_ready",
			Method:       http.MethodGet,
			URL:          cfg.PrometheusURL + "/-/ready",
			WantStatus:   http.StatusOK,
			WantContains: []string{"Prometheus Server is Ready"},
		},
		{
			Name:         "grafana_health",
			Method:       http.MethodGet,
			URL:          cfg.GrafanaURL + "/api/health",
			WantStatus:   http.StatusOK,
			WantContains: []string{`"database"`, `"ok"`},
		},
		{
			Name:         "minio_ready",
			Method:       http.MethodGet,
			URL:          cfg.MinIOURL + "/minio/health/ready",
			WantStatus:   http.StatusOK,
			WantContains: []string{},
		},
		{
			Name:         "mlflow_health",
			Method:       http.MethodGet,
			URL:          cfg.MLflowURL + "/health",
			WantStatus:   http.StatusOK,
			WantContains: []string{"OK"},
		},
	}
}
