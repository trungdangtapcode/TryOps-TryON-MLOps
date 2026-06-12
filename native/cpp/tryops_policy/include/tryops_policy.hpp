#pragma once

#include <map>
#include <string>
#include <unordered_map>
#include <vector>

namespace tryops {

struct MetricGate {
  bool has_min = false;
  double min = 0.0;
  bool has_max = false;
  double max = 0.0;
};

struct Policy {
  std::vector<std::string> required_artifacts;
  std::map<std::string, std::vector<std::string>> required_approvals;
  std::vector<std::string> accepted_risk_statuses;
  int max_critical_vulnerabilities = 0;
  int max_high_vulnerabilities = 0;
  std::map<std::string, std::map<std::string, MetricGate>> metric_gates;
};

struct Candidate {
  std::string candidate_id;
  std::string workload;
  std::string model_name;
  std::string model_version;
  std::unordered_map<std::string, double> metrics;
  std::unordered_map<std::string, std::string> artifacts;
  std::unordered_map<std::string, std::string> metadata;
  std::vector<std::string> approvals;
  std::string risk_status;
  int critical_vulnerabilities = 0;
  int high_vulnerabilities = 0;
  bool signed_artifact = false;
};

struct PromotionDecision {
  bool approved = false;
  std::string target_stage;
  std::vector<std::string> reasons;
};

Policy default_policy();

PromotionDecision evaluate_promotion(
    const Candidate& candidate,
    const std::string& target_stage,
    const Policy& policy = default_policy());

}  // namespace tryops
