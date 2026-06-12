// tryops_perf_stats: native benchmark statistics and SLO verdict engine.
//
// The performance hot path (percentiles, throughput aggregation, SLO gating)
// lives in compiled C++ rather than Python, matching the platform decision that
// Python is the ML lab layer while native code carries the production boundary.
//
// Protocol (matching the other tryops native CLIs): read `key=value` lines from
// stdin, emit one JSON object on stdout, emit `{"error":...}` on stderr with a
// non-zero exit code on failure.
//
// Input keys:
//   samples.latency_ms=12.5,300.1,7556.3        (comma-separated doubles)
//   samples.tokens_per_second=18.5,12.0,20.1    (comma-separated doubles)
//   slo.latency_p95_ms_max=8000                 (optional gate)
//   slo.tokens_per_second_min=10                (optional gate)

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

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

std::vector<double> parse_doubles(const std::string& csv) {
  std::vector<double> values;
  std::stringstream stream(csv);
  std::string token;
  while (std::getline(stream, token, ',')) {
    // trim surrounding whitespace
    const auto begin = token.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
      continue;
    }
    const auto end = token.find_last_not_of(" \t\r\n");
    values.push_back(std::stod(token.substr(begin, end - begin + 1)));
  }
  return values;
}

// Nearest-rank percentile matching the Python `_percentile` helper so the native
// engine and the Python reference agree within rounding tolerance.
double percentile(std::vector<double> values, double quantile) {
  if (values.empty()) {
    throw std::runtime_error("cannot compute percentile of empty sample set");
  }
  std::sort(values.begin(), values.end());
  const double position = (static_cast<double>(values.size()) - 1.0) * quantile;
  long index = std::lround(position);
  if (index < 0) {
    index = 0;
  }
  if (index > static_cast<long>(values.size()) - 1) {
    index = static_cast<long>(values.size()) - 1;
  }
  return values[static_cast<std::size_t>(index)];
}

double mean(const std::vector<double>& values) {
  double total = 0.0;
  for (const double value : values) {
    total += value;
  }
  return total / static_cast<double>(values.size());
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

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    if (payload.find("samples.latency_ms") == payload.end()) {
      throw std::runtime_error("missing required key samples.latency_ms");
    }
    const std::vector<double> latency = parse_doubles(payload.at("samples.latency_ms"));
    if (latency.empty()) {
      throw std::runtime_error("samples.latency_ms produced no values");
    }
    std::vector<double> throughput;
    const auto throughput_it = payload.find("samples.tokens_per_second");
    if (throughput_it != payload.end()) {
      throughput = parse_doubles(throughput_it->second);
    }

    const double p50 = percentile(latency, 0.50);
    const double p95 = percentile(latency, 0.95);
    const double p99 = percentile(latency, 0.99);
    const double lat_min = *std::min_element(latency.begin(), latency.end());
    const double lat_max = *std::max_element(latency.begin(), latency.end());
    const double lat_mean = mean(latency);

    double tps_mean = 0.0;
    double tps_min = 0.0;
    if (!throughput.empty()) {
      tps_mean = mean(throughput);
      tps_min = *std::min_element(throughput.begin(), throughput.end());
    }

    bool have_slo = false;
    bool latency_pass = true;
    bool throughput_pass = true;
    double latency_gate = std::numeric_limits<double>::quiet_NaN();
    double throughput_gate = std::numeric_limits<double>::quiet_NaN();

    const auto latency_gate_it = payload.find("slo.latency_p95_ms_max");
    if (latency_gate_it != payload.end()) {
      have_slo = true;
      latency_gate = std::stod(latency_gate_it->second);
      latency_pass = p95 <= latency_gate;
    }
    const auto throughput_gate_it = payload.find("slo.tokens_per_second_min");
    if (throughput_gate_it != payload.end() && !throughput.empty()) {
      have_slo = true;
      throughput_gate = std::stod(throughput_gate_it->second);
      throughput_pass = tps_mean >= throughput_gate;
    }
    const bool verdict_pass = latency_pass && throughput_pass;

    std::cout.precision(6);
    std::cout << std::fixed;
    std::cout << "{";
    std::cout << "\"schema_version\":\"tryops.native_perf_stats.v1\",";
    std::cout << "\"count\":" << latency.size() << ",";
    std::cout << "\"latency_ms\":{";
    std::cout << "\"p50\":" << p50 << ",\"p95\":" << p95 << ",\"p99\":" << p99 << ",";
    std::cout << "\"min\":" << lat_min << ",\"max\":" << lat_max << ",\"mean\":" << lat_mean << "},";
    std::cout << "\"tokens_per_second\":{";
    std::cout << "\"mean\":" << tps_mean << ",\"min\":" << tps_min << ",";
    std::cout << "\"count\":" << throughput.size() << "},";
    std::cout << "\"slo\":{";
    std::cout << "\"evaluated\":" << (have_slo ? "true" : "false") << ",";
    if (latency_gate_it != payload.end()) {
      std::cout << "\"latency_p95_ms_max\":" << latency_gate << ",";
    }
    std::cout << "\"latency_pass\":" << (latency_pass ? "true" : "false") << ",";
    if (throughput_gate_it != payload.end() && !throughput.empty()) {
      std::cout << "\"tokens_per_second_min\":" << throughput_gate << ",";
    }
    std::cout << "\"throughput_pass\":" << (throughput_pass ? "true" : "false") << ",";
    std::cout << "\"verdict\":\"" << (verdict_pass ? "pass" : "fail") << "\"";
    std::cout << "}";
    std::cout << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
