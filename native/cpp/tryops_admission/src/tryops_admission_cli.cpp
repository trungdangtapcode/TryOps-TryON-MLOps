// Reads an admission wire stream on stdin, runs the controller, prints a JSON
// report on stdout. Exit code: 0 if final breaker state is closed and the shed
// rate is within the optional --max-shed-rate gate, 2 otherwise.
#include "tryops_admission.hpp"

#include <iostream>
#include <sstream>
#include <string>

namespace {

std::string json_double(double value) {
  std::ostringstream out;
  out.setf(std::ios::fixed);
  out.precision(6);
  out << value;
  return out.str();
}

}  // namespace

int main(int argc, char** argv) {
  double max_shed_rate = 1.0;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--max-shed-rate" && i + 1 < argc) {
      max_shed_rate = std::atof(argv[++i]);
    }
  }

  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::AdmissionReport report = tryops::run_admission_wire(buffer.str());

  const bool gate_ok =
      report.final_state == tryops::BreakerState::kClosed &&
      report.shed_rate <= max_shed_rate;

  std::cout << "{";
  std::cout << "\"total\":" << report.total << ",";
  std::cout << "\"admitted\":" << report.admitted << ",";
  std::cout << "\"rejected_rate_limited\":" << report.rejected_rate_limited << ",";
  std::cout << "\"rejected_breaker_open\":" << report.rejected_breaker_open << ",";
  std::cout << "\"rejected_concurrency_full\":" << report.rejected_concurrency_full
            << ",";
  std::cout << "\"breaker_trips\":" << report.breaker_trips << ",";
  std::cout << "\"breaker_recoveries\":" << report.breaker_recoveries << ",";
  std::cout << "\"peak_inflight\":" << report.peak_inflight << ",";
  std::cout << "\"min_tokens\":" << json_double(report.min_tokens) << ",";
  std::cout << "\"admit_rate\":" << json_double(report.admit_rate) << ",";
  std::cout << "\"shed_rate\":" << json_double(report.shed_rate) << ",";
  std::cout << "\"observed_error_rate\":" << json_double(report.observed_error_rate)
            << ",";
  std::cout << "\"final_breaker_state\":\""
            << tryops::breaker_state_name(report.final_state) << "\",";
  std::cout << "\"max_shed_rate\":" << json_double(max_shed_rate) << ",";
  std::cout << "\"gate_ok\":" << (gate_ok ? "true" : "false");
  std::cout << "}\n";

  return gate_ok ? 0 : 2;
}
