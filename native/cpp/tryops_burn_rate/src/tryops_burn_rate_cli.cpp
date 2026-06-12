// tryops_burn_rate: native multi-window SLO burn-rate evaluator.
//
// Python marshals SLI counts from local artifacts; compiled C++ computes
// long-window + short-window burn rates and alert verdicts. This mirrors the
// production boundary pattern used by the other TryOps native engines.
//
// Input protocol:
//   slo.name=llm
//   slo.error_budget_ratio=0.01
//   windows=page_fast,page_slow,ticket
//   window.page_fast.long_bad=2
//   window.page_fast.long_total=100
//   window.page_fast.short_bad=1
//   window.page_fast.short_total=20
//   window.page_fast.threshold=14.4
//   window.page_fast.severity=page

#include <algorithm>
#include <cmath>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

struct Side {
  double bad = 0.0;
  double total = 0.0;
  double error_ratio = 0.0;
  double burn_rate = 0.0;
};

struct Window {
  std::string name;
  std::string severity;
  double threshold = 0.0;
  Side long_side;
  Side short_side;
  bool firing = false;
};

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    if (ch == '\\' || ch == '"') {
      out << '\\' << ch;
    } else {
      out << ch;
    }
  }
  return out.str();
}

std::unordered_map<std::string, std::string> read_payload() {
  std::unordered_map<std::string, std::string> values;
  std::string line;
  while (std::getline(std::cin, line)) {
    const auto separator = line.find('=');
    if (separator == std::string::npos) {
      continue;
    }
    values[line.substr(0, separator)] = line.substr(separator + 1);
  }
  return values;
}

std::vector<std::string> split_csv(const std::string& csv) {
  std::vector<std::string> values;
  std::stringstream stream(csv);
  std::string token;
  while (std::getline(stream, token, ',')) {
    const auto begin = token.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
      continue;
    }
    const auto end = token.find_last_not_of(" \t\r\n");
    values.push_back(token.substr(begin, end - begin + 1));
  }
  return values;
}

std::string get_string(
    const std::unordered_map<std::string, std::string>& values,
    const std::string& key) {
  const auto it = values.find(key);
  if (it == values.end()) {
    throw std::runtime_error("missing required key " + key);
  }
  return it->second;
}

double get_double(
    const std::unordered_map<std::string, std::string>& values,
    const std::string& key) {
  return std::stod(get_string(values, key));
}

Side compute_side(double bad, double total, double error_budget_ratio) {
  if (total <= 0.0) {
    throw std::runtime_error("window total must be greater than zero");
  }
  if (bad < 0.0 || bad > total) {
    throw std::runtime_error("bad events must be between zero and total events");
  }
  if (error_budget_ratio <= 0.0 || error_budget_ratio >= 1.0) {
    throw std::runtime_error("slo.error_budget_ratio must be between zero and one");
  }
  Side side;
  side.bad = bad;
  side.total = total;
  side.error_ratio = bad / total;
  side.burn_rate = side.error_ratio / error_budget_ratio;
  return side;
}

int severity_rank(const std::string& severity) {
  if (severity == "page") {
    return 3;
  }
  if (severity == "ticket") {
    return 2;
  }
  if (severity == "warning") {
    return 1;
  }
  return 0;
}

void write_side(const Side& side) {
  std::cout << "{";
  std::cout << "\"bad\":" << side.bad << ",";
  std::cout << "\"total\":" << side.total << ",";
  std::cout << "\"error_ratio\":" << side.error_ratio << ",";
  std::cout << "\"burn_rate\":" << side.burn_rate;
  std::cout << "}";
}

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    const std::string slo_name = get_string(payload, "slo.name");
    const double error_budget_ratio = get_double(payload, "slo.error_budget_ratio");
    const std::vector<std::string> names = split_csv(get_string(payload, "windows"));
    if (names.empty()) {
      throw std::runtime_error("windows cannot be empty");
    }

    std::vector<Window> windows;
    std::string verdict = "ok";
    int verdict_rank = 0;
    for (const std::string& name : names) {
      const std::string prefix = "window." + name + ".";
      Window window;
      window.name = name;
      window.severity = get_string(payload, prefix + "severity");
      window.threshold = get_double(payload, prefix + "threshold");
      window.long_side = compute_side(
          get_double(payload, prefix + "long_bad"),
          get_double(payload, prefix + "long_total"),
          error_budget_ratio);
      window.short_side = compute_side(
          get_double(payload, prefix + "short_bad"),
          get_double(payload, prefix + "short_total"),
          error_budget_ratio);
      window.firing = window.long_side.burn_rate >= window.threshold &&
                      window.short_side.burn_rate >= window.threshold;
      if (window.firing && severity_rank(window.severity) > verdict_rank) {
        verdict = window.severity;
        verdict_rank = severity_rank(window.severity);
      }
      windows.push_back(window);
    }

    std::cout.precision(6);
    std::cout << std::fixed;
    std::cout << "{";
    std::cout << "\"schema_version\":\"tryops.native_burn_rate.v1\",";
    std::cout << "\"slo\":{\"name\":\"" << json_escape(slo_name) << "\",";
    std::cout << "\"error_budget_ratio\":" << error_budget_ratio << "},";
    std::cout << "\"verdict\":\"" << verdict << "\",";
    std::cout << "\"windows\":[";
    bool first = true;
    for (const Window& window : windows) {
      if (!first) {
        std::cout << ",";
      }
      first = false;
      std::cout << "{";
      std::cout << "\"name\":\"" << json_escape(window.name) << "\",";
      std::cout << "\"severity\":\"" << json_escape(window.severity) << "\",";
      std::cout << "\"threshold\":" << window.threshold << ",";
      std::cout << "\"long\":";
      write_side(window.long_side);
      std::cout << ",\"short\":";
      write_side(window.short_side);
      std::cout << ",\"firing\":" << (window.firing ? "true" : "false");
      std::cout << "}";
    }
    std::cout << "]}";
    std::cout << "\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
