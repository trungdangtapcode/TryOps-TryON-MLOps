#include "tryops_trace_envelope.hpp"

#include <iostream>
#include <string>
#include <vector>

int main() {
  std::vector<std::string> lines;
  std::string line;
  while (std::getline(std::cin, line)) {
    if (!line.empty()) {
      lines.push_back(line);
    }
  }
  const auto envelope = tryops::parse_trace_envelope_lines(lines);
  const auto validation = tryops::validate_trace_envelope(envelope);
  std::cout << tryops::validation_report_to_json(envelope, validation) << "\n";
  return validation.passed ? 0 : 2;
}
