package main

var llmPayload = []byte(`{
  "request_id": "req-fullstack-load-llm",
  "prompt": "Summarize TryOps production load-test posture in one paragraph.",
  "model_alias": "baseline",
  "max_tokens": 32,
  "fallback_enabled": true,
  "optimized_available": false,
  "semantic_cache_enabled": false,
  "quota_plan": "enterprise",
  "user_id": "fullstack-load-user"
}`)

var promotionPayload = []byte(`{
  "request_id": "req-fullstack-load-promotion",
  "api_key": "tryops-operator-demo-key",
  "target_stage": "staging",
  "candidate": {
    "candidate_id": "vton-fullstack-load-001",
    "workload": "vton",
    "model_name": "catvton-baseline",
    "model_version": "0.1.0",
    "metrics": {
      "garment_fidelity": 0.81,
      "identity_preservation": 0.78,
      "artifact_rate": 0.08,
      "latency_p95_ms": 9300
    },
    "artifacts": {
      "model_card": "s3://tryops-artifacts/model-cards/vton-load.md",
      "data_card": "s3://tryops-artifacts/data-cards/vitonhd-demo-v1.md",
      "evaluation_report": "s3://tryops-artifacts/reports/vton-load.json",
      "sbom": "s3://tryops-artifacts/sbom/vton-load.spdx.json",
      "model_artifact_scan": "s3://tryops-artifacts/model-scans/vton-load.json",
      "model_provenance": "s3://tryops-artifacts/provenance/vton-load.model-provenance.json"
    },
    "approvals": ["mlops_owner", "risk_owner"],
    "risk_status": "medium_approved",
    "vulnerabilities": {"critical": 0, "high": 0},
    "signed": true,
    "metadata": {
      "code_version": "local-dev",
      "dataset_version": "vitonhd-demo-v1",
      "pipeline_run_id": "run-vton-load",
      "container_digest": "sha256:demo",
      "model_provenance": {"verified": true},
      "model_artifacts": {"scan_status": "passed", "unsafe_file_count": 0}
    }
  }
}`)

func jsonHeaders() map[string]string {
	return map[string]string{"Content-Type": "application/json"}
}

func signedHeaders() map[string]string {
	headers := jsonHeaders()
	headers["x-tryops-artifact-signed"] = "true"
	return headers
}
