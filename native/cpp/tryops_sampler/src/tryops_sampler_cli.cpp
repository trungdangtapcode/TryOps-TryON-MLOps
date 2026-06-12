// Reads a trace wire stream, samples it, prints a JSON report. The kept sample
// ids are emitted so the selection is auditable/reproducible. Exit always 0.
#include "tryops_sampler.hpp"

#include <iostream>
#include <sstream>
#include <string>

namespace {

std::string json_escape(const std::string& v) {
  std::ostringstream out;
  for (char c : v) {
    if (c == '"' || c == '\\') {
      out << '\\' << c;
    } else {
      out << c;
    }
  }
  return out.str();
}

}  // namespace

int main() {
  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::SamplerReport r = tryops::run_sampler_wire(buffer.str());

  std::cout << "{";
  std::cout << "\"observed\":" << r.observed << ",";
  std::cout << "\"capacity\":" << r.capacity << ",";
  std::cout << "\"kept\":" << r.sample.size() << ",";
  std::cout << "\"priority_seen\":" << r.priority_seen << ",";
  std::cout << "\"priority_kept\":" << r.priority_kept << ",";
  std::cout << "\"sample\":[";
  for (std::size_t i = 0; i < r.sample.size(); ++i) {
    if (i != 0) std::cout << ",";
    std::cout << "\"" << json_escape(r.sample[i]) << "\"";
  }
  std::cout << "]}";
  std::cout << "\n";
  return 0;
}
