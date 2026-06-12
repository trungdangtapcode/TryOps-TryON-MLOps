#include "tryops_policy.hpp"

#include <cstdlib>
#include <sstream>

namespace tryops {
namespace {

bool contains(const std::vector<std::string>& values, const std::string& needle) {
  for (const auto& value : values) {
    if (value == needle) {
      return true;
    }
  }
  return false;
}

std::string metadata_value(
    const Candidate& candidate,
    const std::string& key,
    const std::string& fallback = "") {
  const auto found = candidate.metadata.find(key);
  if (found == candidate.metadata.end()) {
    return fallback;
  }
  return found->second;
}

int metadata_int(const Candidate& candidate, const std::string& key, int fallback = 0) {
  const auto value = metadata_value(candidate, key, "");
  if (value.empty()) {
    return fallback;
  }
  return std::atoi(value.c_str());
}

std::string join(const std::vector<std::string>& values, const std::string& separator) {
  std::ostringstream out;
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0) {
      out << separator;
    }
    out << values[index];
  }
  return out.str();
}

std::string double_to_string(double value) {
  std::ostringstream out;
  out << value;
  return out.str();
}

}  // namespace

Policy default_policy() {
  Policy policy;
  policy.required_artifacts = {
      "model_card", "data_card", "evaluation_report", "sbom", "model_provenance"};
  policy.required_approvals = {
      {"staging", {"mlops_owner"}},
      {"champion", {"mlops_owner", "risk_owner"}},
  };
  policy.accepted_risk_statuses = {"low", "medium_approved"};
  policy.max_critical_vulnerabilities = 0;
  policy.max_high_vulnerabilities = 0;

  policy.metric_gates["vton"] = {
      {"garment_fidelity", MetricGate{true, 0.72, false, 0.0}},
      {"identity_preservation", MetricGate{true, 0.70, false, 0.0}},
      {"artifact_rate", MetricGate{false, 0.0, true, 0.12}},
      {"latency_p95_ms", MetricGate{false, 0.0, true, 12000.0}},
  };

  policy.metric_gates["llm"] = {
      {"quality_score", MetricGate{true, 0.78, false, 0.0}},
      {"tokens_per_second", MetricGate{true, 20.0, false, 0.0}},
      {"latency_p95_ms", MetricGate{false, 0.0, true, 2500.0}},
      {"memory_gb", MetricGate{false, 0.0, true, 16.0}},
  };

  return policy;
}

PromotionDecision evaluate_promotion(
    const Candidate& candidate,
    const std::string& target_stage,
    const Policy& policy) {
  PromotionDecision decision;
  decision.target_stage = target_stage;

  if (policy.metric_gates.find(candidate.workload) == policy.metric_gates.end()) {
    decision.reasons.push_back("unknown workload '" + candidate.workload + "'");
  }

  std::vector<std::string> missing_artifacts;
  for (const auto& artifact : policy.required_artifacts) {
    const auto found = candidate.artifacts.find(artifact);
    if (found == candidate.artifacts.end() || found->second.empty()) {
      missing_artifacts.push_back(artifact);
    }
  }
  if (!missing_artifacts.empty()) {
    decision.reasons.push_back("missing required artifacts: " + join(missing_artifacts, ", "));
  }

  const auto approvals_for_stage = policy.required_approvals.find(target_stage);
  if (approvals_for_stage == policy.required_approvals.end()) {
    decision.reasons.push_back("unknown target stage '" + target_stage + "'");
  } else {
    std::vector<std::string> missing_approvals;
    for (const auto& approval : approvals_for_stage->second) {
      if (!contains(candidate.approvals, approval)) {
        missing_approvals.push_back(approval);
      }
    }
    if (!missing_approvals.empty()) {
      decision.reasons.push_back("missing approvals: " + join(missing_approvals, ", "));
    }
  }

  if (!contains(policy.accepted_risk_statuses, candidate.risk_status)) {
    decision.reasons.push_back("unaccepted risk status '" + candidate.risk_status + "'");
  }

  std::vector<std::string> vulnerability_failures;
  if (candidate.critical_vulnerabilities > policy.max_critical_vulnerabilities) {
    vulnerability_failures.push_back(
        "critical vulnerabilities " + std::to_string(candidate.critical_vulnerabilities) +
        " > " + std::to_string(policy.max_critical_vulnerabilities));
  }
  if (candidate.high_vulnerabilities > policy.max_high_vulnerabilities) {
    vulnerability_failures.push_back(
        "high vulnerabilities " + std::to_string(candidate.high_vulnerabilities) +
        " > " + std::to_string(policy.max_high_vulnerabilities));
  }
  if (!vulnerability_failures.empty()) {
    decision.reasons.push_back(join(vulnerability_failures, "; "));
  }

  if (!candidate.signed_artifact) {
    decision.reasons.push_back("candidate artifact is not signed");
  }

  if (candidate.workload == "vton" || candidate.workload == "llm") {
    std::vector<std::string> provenance_failures;
    const auto provenance = candidate.artifacts.find("model_provenance");
    if (provenance == candidate.artifacts.end() || provenance->second.empty()) {
      provenance_failures.push_back("missing required model provenance: model_provenance");
    }
    const auto provenance_status =
        metadata_value(candidate, "model_provenance.status", "missing");
    if (provenance_status != "passed") {
      provenance_failures.push_back(
          "model provenance status '" + provenance_status + "' is not accepted");
    }
    const auto statement_type =
        metadata_value(candidate, "model_provenance.statement_type", "missing");
    if (statement_type != "https://in-toto.io/Statement/v1") {
      provenance_failures.push_back(
          "model provenance statement type '" + statement_type +
          "' != 'https://in-toto.io/Statement/v1'");
    }
    const auto predicate_type =
        metadata_value(candidate, "model_provenance.predicate_type", "missing");
    if (predicate_type != "https://slsa.dev/provenance/v1") {
      provenance_failures.push_back(
          "model provenance predicate type '" + predicate_type +
          "' != 'https://slsa.dev/provenance/v1'");
    }
    const auto signature_mode =
        metadata_value(candidate, "model_provenance.signature_mode", "missing");
    if (signature_mode != "local-dsse-digest" && signature_mode != "sigstore-keyless-oidc") {
      provenance_failures.push_back(
          "model provenance signature mode '" + signature_mode + "' is not accepted");
    }
    const auto signer_identity =
        metadata_value(candidate, "model_provenance.signer_identity", "");
    if (signer_identity.empty()) {
      provenance_failures.push_back("model provenance signer identity is missing");
    }
    const auto verified = metadata_value(candidate, "model_provenance.verified", "false");
    if (verified != "true" && verified != "1" && verified != "yes" && verified != "passed") {
      provenance_failures.push_back("model provenance verification did not pass");
    }
    if (!provenance_failures.empty()) {
      decision.reasons.push_back(join(provenance_failures, "; "));
    }
  }

  if (candidate.workload == "vton" || candidate.workload == "llm") {
    std::vector<std::string> model_artifact_failures;
    const auto scan = candidate.artifacts.find("model_artifact_scan");
    if (scan == candidate.artifacts.end() || scan->second.empty()) {
      model_artifact_failures.push_back("missing required model artifact scan: model_artifact_scan");
    }
    const auto artifact_policy =
        metadata_value(candidate, "model_artifacts.serialization_policy", "missing");
    if (artifact_policy != "safetensors_only") {
      model_artifact_failures.push_back(
          "model artifact policy '" + artifact_policy + "' != 'safetensors_only'");
    }
    const auto scan_status = metadata_value(candidate, "model_artifacts.scan_status", "missing");
    if (scan_status != "passed") {
      model_artifact_failures.push_back(
          "model artifact scan status '" + scan_status + "' is not passed");
    }
    const int unsafe_file_count = metadata_int(candidate, "model_artifacts.unsafe_file_count", 0);
    if (unsafe_file_count > 0) {
      model_artifact_failures.push_back(
          "unsafe model artifact files " + std::to_string(unsafe_file_count) + " > 0");
    }
    const int safetensors_files = metadata_int(candidate, "model_artifacts.safetensors_files", 0);
    if (safetensors_files < 1) {
      model_artifact_failures.push_back(
          "safetensors files " + std::to_string(safetensors_files) + " < 1");
    }
    const auto rejected_extensions =
        metadata_value(candidate, "model_artifacts.rejected_extensions", "");
    if (!rejected_extensions.empty()) {
      model_artifact_failures.push_back(
          "rejected model artifact extensions: " + rejected_extensions);
    }
    if (!model_artifact_failures.empty()) {
      decision.reasons.push_back(join(model_artifact_failures, "; "));
    }
  }

  const auto workload_gates = policy.metric_gates.find(candidate.workload);
  if (workload_gates != policy.metric_gates.end()) {
    std::vector<std::string> metric_failures;
    for (const auto& [metric_name, gate] : workload_gates->second) {
      const auto found = candidate.metrics.find(metric_name);
      if (found == candidate.metrics.end()) {
        metric_failures.push_back("missing metric '" + metric_name + "'");
        continue;
      }

      const double value = found->second;
      if (gate.has_min && value < gate.min) {
        metric_failures.push_back(
            metric_name + " " + double_to_string(value) + " < " + double_to_string(gate.min));
      }
      if (gate.has_max && value > gate.max) {
        metric_failures.push_back(
            metric_name + " " + double_to_string(value) + " > " + double_to_string(gate.max));
      }
    }

    if (!metric_failures.empty()) {
      decision.reasons.push_back(join(metric_failures, "; "));
    }
  }

  decision.approved = decision.reasons.empty();
  if (decision.approved) {
    decision.reasons.push_back("all promotion gates passed");
  }
  return decision;
}

}  // namespace tryops
