package tryops.promotion

default allow := false

required_artifacts := {"model_card", "data_card", "evaluation_report", "sbom", "model_artifact_scan", "model_provenance"}
accepted_risk_statuses := {"low", "medium_approved"}

allow if {
  no_missing_artifacts
  no_blocking_vulnerabilities
  input.candidate.signed == true
  model_provenance_pass
  model_artifact_scan_pass
  accepted_risk_statuses[input.candidate.risk_status]
  required_approvals_present
  workload_metrics_pass
}

no_missing_artifacts if {
  count(required_artifacts - {name | input.candidate.artifacts[name]}) == 0
}

no_blocking_vulnerabilities if {
  input.candidate.vulnerabilities.critical == 0
  input.candidate.vulnerabilities.high == 0
}

model_artifact_scan_pass if {
  input.candidate.metadata.model_artifacts.serialization_policy == "safetensors_only"
  input.candidate.metadata.model_artifacts.scan_status == "passed"
  input.candidate.metadata.model_artifacts.unsafe_file_count == 0
  input.candidate.metadata.model_artifacts.safetensors_files >= 1
  count(input.candidate.metadata.model_artifacts.rejected_extensions) == 0
}

model_provenance_pass if {
  input.candidate.metadata.model_provenance.status == "passed"
  input.candidate.metadata.model_provenance.statement_type == "https://in-toto.io/Statement/v1"
  input.candidate.metadata.model_provenance.predicate_type == "https://slsa.dev/provenance/v1"
  input.candidate.metadata.model_provenance.signature_mode in {"local-dsse-digest", "sigstore-keyless-oidc"}
  input.candidate.metadata.model_provenance.signer_identity != ""
  input.candidate.metadata.model_provenance.verified == true
}

required_approvals_present if {
  input.target_stage == "staging"
  "mlops_owner" in input.candidate.approvals
}

required_approvals_present if {
  input.target_stage == "champion"
  "mlops_owner" in input.candidate.approvals
  "risk_owner" in input.candidate.approvals
}

workload_metrics_pass if {
  input.candidate.workload == "vton"
  input.candidate.metrics.garment_fidelity >= 0.72
  input.candidate.metrics.identity_preservation >= 0.70
  input.candidate.metrics.artifact_rate <= 0.12
  input.candidate.metrics.latency_p95_ms <= 12000
}

workload_metrics_pass if {
  input.candidate.workload == "llm"
  input.candidate.metrics.quality_score >= 0.78
  input.candidate.metrics.tokens_per_second >= 20
  input.candidate.metrics.latency_p95_ms <= 2500
  input.candidate.metrics.memory_gb <= 16
}
