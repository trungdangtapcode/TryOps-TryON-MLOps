#include <algorithm>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

namespace {

struct Scenario {
  std::string id;
  std::string type;
  std::string workload;
};

struct Verdict {
  Scenario scenario;
  std::string failure_mode;
  std::string severity;
  std::string expected_signal;
  int bad_events = 0;
  int total_events = 100;
  bool rollback_required = false;
};

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
        if (static_cast<unsigned char>(ch) < 0x20) {
          out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
              << static_cast<int>(static_cast<unsigned char>(ch));
        } else {
          out << ch;
        }
        break;
    }
  }
  return out.str();
}

std::string lower_ascii(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  return value;
}

int get_int(const std::map<std::string, std::string>& payload, const std::string& key, int default_value) {
  const auto found = payload.find(key);
  if (found == payload.end()) {
    return default_value;
  }
  try {
    return std::stoi(found->second);
  } catch (...) {
    return default_value;
  }
}

std::string get_string(const std::map<std::string, std::string>& payload, const std::string& key) {
  const auto found = payload.find(key);
  return found == payload.end() ? "" : found->second;
}

std::vector<Scenario> parse_scenarios(const std::map<std::string, std::string>& payload) {
  const int scenario_count = std::max(0, get_int(payload, "scenario_count", 0));
  std::vector<Scenario> scenarios;
  scenarios.reserve(static_cast<std::size_t>(scenario_count));
  for (int index = 0; index < scenario_count; ++index) {
    const std::string prefix = "scenario." + std::to_string(index) + ".";
    Scenario scenario;
    scenario.id = get_string(payload, prefix + "id");
    scenario.type = lower_ascii(get_string(payload, prefix + "type"));
    scenario.workload = lower_ascii(get_string(payload, prefix + "workload"));
    if (!scenario.id.empty() && !scenario.type.empty()) {
      if (scenario.workload.empty()) {
        scenario.workload = "llm";
      }
      scenarios.push_back(scenario);
    }
  }
  return scenarios;
}

Verdict evaluate(const Scenario& scenario) {
  Verdict verdict;
  verdict.scenario = scenario;

  if (scenario.type == "gpu_oom") {
    verdict.failure_mode = "resource_exhaustion";
    verdict.severity = "page";
    verdict.expected_signal = "oom_rejections_and_timeout_spike";
    verdict.bad_events = 30;
    verdict.rollback_required = true;
  } else if (scenario.type == "slow_decode") {
    verdict.failure_mode = "latency_regression";
    verdict.severity = "page";
    verdict.expected_signal = "decode_latency_p95_breach";
    verdict.bad_events = 20;
    verdict.rollback_required = true;
  } else if (scenario.type == "corrupted_weights") {
    verdict.failure_mode = "model_load_failure";
    verdict.severity = "page";
    verdict.expected_signal = "readiness_failure_and_generation_errors";
    verdict.bad_events = 100;
    verdict.rollback_required = true;
  } else if (scenario.type == "poisoned_candidate") {
    verdict.failure_mode = "quality_or_safety_regression";
    verdict.severity = "page";
    verdict.expected_signal = "promotion_or_guardrail_failure";
    verdict.bad_events = 25;
    verdict.rollback_required = true;
  } else {
    verdict.failure_mode = "unknown_fault";
    verdict.severity = "ticket";
    verdict.expected_signal = "manual_review_required";
    verdict.bad_events = 1;
    verdict.rollback_required = false;
  }

  return verdict;
}

void print_json(const std::vector<Verdict>& verdicts) {
  bool passed = true;
  int rollback_required = 0;
  for (const auto& verdict : verdicts) {
    if (verdict.bad_events <= 0 || verdict.total_events <= 0) {
      passed = false;
    }
    if (verdict.rollback_required) {
      ++rollback_required;
    }
  }

  std::cout << "{";
  std::cout << "\"schema_version\":\"tryops.native_chaos.v1\",";
  std::cout << "\"engine\":{\"name\":\"tryops_chaos\",\"language\":\"c++\",\"version\":\"0.1.0\"},";
  std::cout << "\"passed\":" << (passed ? "true" : "false") << ",";
  std::cout << "\"scenario_count\":" << verdicts.size() << ",";
  std::cout << "\"rollback_required_count\":" << rollback_required << ",";
  std::cout << "\"scenarios\":[";
  for (std::size_t index = 0; index < verdicts.size(); ++index) {
    if (index > 0) {
      std::cout << ",";
    }
    const auto& verdict = verdicts[index];
    std::cout << "{";
    std::cout << "\"id\":\"" << json_escape(verdict.scenario.id) << "\",";
    std::cout << "\"type\":\"" << json_escape(verdict.scenario.type) << "\",";
    std::cout << "\"workload\":\"" << json_escape(verdict.scenario.workload) << "\",";
    std::cout << "\"failure_mode\":\"" << json_escape(verdict.failure_mode) << "\",";
    std::cout << "\"severity\":\"" << json_escape(verdict.severity) << "\",";
    std::cout << "\"expected_signal\":\"" << json_escape(verdict.expected_signal) << "\",";
    std::cout << "\"bad_events\":" << verdict.bad_events << ",";
    std::cout << "\"total_events\":" << verdict.total_events << ",";
    std::cout << "\"rollback_required\":" << (verdict.rollback_required ? "true" : "false");
    std::cout << "}";
  }
  std::cout << "]}";
  std::cout << "\n";
}

}  // namespace

int main() {
  std::map<std::string, std::string> payload;
  std::string line;
  while (std::getline(std::cin, line)) {
    const auto separator = line.find('=');
    if (separator == std::string::npos) {
      continue;
    }
    payload[line.substr(0, separator)] = line.substr(separator + 1);
  }

  const auto scenarios = parse_scenarios(payload);
  std::vector<Verdict> verdicts;
  verdicts.reserve(scenarios.size());
  for (const auto& scenario : scenarios) {
    verdicts.push_back(evaluate(scenario));
  }
  print_json(verdicts);
  return 0;
}
