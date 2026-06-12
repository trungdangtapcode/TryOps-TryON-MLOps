#include "tryops_policy.hpp"

#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>

namespace {

bool starts_with(const std::string& value, const std::string& prefix) {
  return value.rfind(prefix, 0) == 0;
}

std::string strip_prefix(const std::string& value, const std::string& prefix) {
  return value.substr(prefix.size());
}

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    switch (ch) {
      case '\\':
        out << "\\\\";
        break;
      case '"':
        out << "\\\"";
        break;
      case '\n':
        out << "\\n";
        break;
      case '\r':
        out << "\\r";
        break;
      case '\t':
        out << "\\t";
        break;
      default:
        out << ch;
        break;
    }
  }
  return out.str();
}

bool parse_bool(const std::string& value) {
  return value == "true" || value == "1" || value == "yes";
}

void apply_line(
    const std::string& line,
    tryops::Candidate& candidate,
    std::string& target_stage) {
  const auto separator = line.find('=');
  if (separator == std::string::npos) {
    return;
  }
  const std::string key = line.substr(0, separator);
  const std::string value = line.substr(separator + 1);

  if (key == "target_stage") {
    target_stage = value;
  } else if (key == "candidate_id") {
    candidate.candidate_id = value;
  } else if (key == "workload") {
    candidate.workload = value;
  } else if (key == "model_name") {
    candidate.model_name = value;
  } else if (key == "model_version") {
    candidate.model_version = value;
  } else if (key == "risk_status") {
    candidate.risk_status = value;
  } else if (key == "signed") {
    candidate.signed_artifact = parse_bool(value);
  } else if (key == "critical_vulnerabilities") {
    candidate.critical_vulnerabilities = std::atoi(value.c_str());
  } else if (key == "high_vulnerabilities") {
    candidate.high_vulnerabilities = std::atoi(value.c_str());
  } else if (key == "approval") {
    candidate.approvals.push_back(value);
  } else if (starts_with(key, "metric.")) {
    candidate.metrics[strip_prefix(key, "metric.")] = std::atof(value.c_str());
  } else if (starts_with(key, "artifact.")) {
    candidate.artifacts[strip_prefix(key, "artifact.")] = value;
  } else if (starts_with(key, "metadata.")) {
    candidate.metadata[strip_prefix(key, "metadata.")] = value;
  }
}

void print_json_decision(const tryops::PromotionDecision& decision) {
  std::cout << "{";
  std::cout << "\"approved\":" << (decision.approved ? "true" : "false") << ",";
  std::cout << "\"target_stage\":\"" << json_escape(decision.target_stage) << "\",";
  std::cout << "\"reasons\":[";
  for (std::size_t index = 0; index < decision.reasons.size(); ++index) {
    if (index != 0) {
      std::cout << ",";
    }
    std::cout << "\"" << json_escape(decision.reasons[index]) << "\"";
  }
  std::cout << "]}";
  std::cout << "\n";
}

}  // namespace

int main() {
  tryops::Candidate candidate;
  std::string target_stage = "staging";
  std::string line;
  while (std::getline(std::cin, line)) {
    apply_line(line, candidate, target_stage);
  }

  const auto decision = tryops::evaluate_promotion(candidate, target_stage);
  print_json_decision(decision);
  return decision.approved ? 0 : 2;
}
