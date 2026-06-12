#include "tryops_policy.hpp"

#include <cassert>
#include <iostream>
#include <string>

namespace {

tryops::Candidate good_vton_candidate() {
  tryops::Candidate candidate;
  candidate.candidate_id = "vton-catvton-2026-06-11-001";
  candidate.workload = "vton";
  candidate.model_name = "catvton-baseline";
  candidate.model_version = "0.1.0";
  candidate.metrics = {
      {"garment_fidelity", 0.81},
      {"identity_preservation", 0.78},
      {"artifact_rate", 0.08},
      {"latency_p95_ms", 9300.0},
  };
  candidate.artifacts = {
      {"model_card", "s3://tryops-artifacts/model-cards/vton-catvton-001.md"},
      {"data_card", "s3://tryops-artifacts/data-cards/vitonhd-demo-v1.md"},
      {"evaluation_report", "s3://tryops-artifacts/reports/vton-catvton-001.json"},
      {"sbom", "s3://tryops-artifacts/sbom/vton-catvton-001.spdx.json"},
      {"model_artifact_scan", "s3://tryops-artifacts/model-scans/vton-catvton-001.json"},
      {"model_provenance", "s3://tryops-artifacts/provenance/vton-catvton-001.model-provenance.json"},
  };
  candidate.metadata = {
      {"model_provenance.status", "passed"},
      {"model_provenance.statement_type", "https://in-toto.io/Statement/v1"},
      {"model_provenance.predicate_type", "https://slsa.dev/provenance/v1"},
      {"model_provenance.signature_mode", "local-dsse-digest"},
      {"model_provenance.signer_identity", "tryops-local-ci"},
      {"model_provenance.verified", "true"},
      {"model_artifacts.serialization_policy", "safetensors_only"},
      {"model_artifacts.scan_status", "passed"},
      {"model_artifacts.unsafe_file_count", "0"},
      {"model_artifacts.safetensors_files", "1"},
      {"model_artifacts.rejected_extensions", ""},
  };
  candidate.approvals = {"mlops_owner", "risk_owner"};
  candidate.risk_status = "medium_approved";
  candidate.critical_vulnerabilities = 0;
  candidate.high_vulnerabilities = 0;
  candidate.signed_artifact = true;
  return candidate;
}

tryops::Candidate bad_vton_candidate() {
  tryops::Candidate candidate = good_vton_candidate();
  candidate.candidate_id = "vton-catvton-2026-06-11-bad";
  candidate.metrics["garment_fidelity"] = 0.61;
  candidate.metrics["identity_preservation"] = 0.65;
  candidate.metrics["artifact_rate"] = 0.21;
  candidate.metrics["latency_p95_ms"] = 18100.0;
  candidate.artifacts.erase("data_card");
  candidate.artifacts.erase("sbom");
  candidate.approvals = {"mlops_owner"};
  candidate.risk_status = "unreviewed";
  candidate.critical_vulnerabilities = 1;
  candidate.high_vulnerabilities = 2;
  candidate.signed_artifact = false;
  return candidate;
}

bool contains_reason(const tryops::PromotionDecision& decision, const std::string& needle) {
  for (const auto& reason : decision.reasons) {
    if (reason.find(needle) != std::string::npos) {
      return true;
    }
  }
  return false;
}

}  // namespace

int main() {
  const auto good = tryops::evaluate_promotion(good_vton_candidate(), "champion");
  assert(good.approved);
  assert(good.reasons.size() == 1);
  assert(good.reasons[0] == "all promotion gates passed");

  const auto bad = tryops::evaluate_promotion(bad_vton_candidate(), "champion");
  assert(!bad.approved);
  assert(contains_reason(bad, "missing required artifacts"));
  assert(contains_reason(bad, "missing approvals"));
  assert(contains_reason(bad, "unaccepted risk status"));
  assert(contains_reason(bad, "critical vulnerabilities"));
  assert(contains_reason(bad, "candidate artifact is not signed"));
  assert(contains_reason(bad, "garment_fidelity"));

  const auto unknown = tryops::evaluate_promotion(good_vton_candidate(), "production");
  assert(!unknown.approved);
  assert(contains_reason(unknown, "unknown target stage"));

  std::cout << "native tryops_policy tests passed\n";
  return 0;
}
