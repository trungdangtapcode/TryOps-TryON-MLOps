// Reads a retry wire stream, simulates the retry policy, prints JSON. Exit 0 if
// the final success rate meets --min-success-rate, else 2.
#include "tryops_retry.hpp"

#include <iostream>
#include <sstream>
#include <string>

namespace {
std::string num(double v) {
  std::ostringstream out;
  out.setf(std::ios::fixed);
  out.precision(6);
  out << v;
  return out.str();
}
}  // namespace

int main(int argc, char** argv) {
  double min_success_rate = 0.0;
  for (int i = 1; i < argc; ++i) {
    if (std::string(argv[i]) == "--min-success-rate" && i + 1 < argc) {
      min_success_rate = std::atof(argv[++i]);
    }
  }

  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::RetryReport r = tryops::run_retry_wire(buffer.str());

  const bool gate_ok = r.success_rate >= min_success_rate;

  std::cout << "{";
  std::cout << "\"requests\":" << r.requests << ",";
  std::cout << "\"successes\":" << r.successes << ",";
  std::cout << "\"failures\":" << r.failures << ",";
  std::cout << "\"retries_attempted\":" << r.retries_attempted << ",";
  std::cout << "\"retries_denied_budget\":" << r.retries_denied_budget << ",";
  std::cout << "\"retries_exhausted\":" << r.retries_exhausted << ",";
  std::cout << "\"total_backoff_ms\":" << num(r.total_backoff_ms) << ",";
  std::cout << "\"success_rate\":" << num(r.success_rate) << ",";
  std::cout << "\"success_rate_without_retry\":" << num(r.success_rate_without_retry) << ",";
  std::cout << "\"min_success_rate\":" << num(min_success_rate) << ",";
  std::cout << "\"gate_ok\":" << (gate_ok ? "true" : "false");
  std::cout << "}\n";
  return gate_ok ? 0 : 2;
}
