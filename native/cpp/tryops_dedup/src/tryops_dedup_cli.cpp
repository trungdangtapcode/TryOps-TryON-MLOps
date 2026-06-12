// Reads a key stream (optional `expected_items=`/`target_fp_rate=` header, then
// one idempotency key per line) and prints dedup stats as JSON.
// Exit 0 if observed false-positive rate stays within --max-fp-rate, else 2.
#include "tryops_dedup.hpp"

#include <iostream>
#include <sstream>
#include <string>

namespace {

std::string json_double(double v) {
  std::ostringstream out;
  out.setf(std::ios::fixed);
  out.precision(6);
  out << v;
  return out.str();
}

}  // namespace

int main(int argc, char** argv) {
  double max_fp_rate = 1.0;
  for (int i = 1; i < argc; ++i) {
    if (std::string(argv[i]) == "--max-fp-rate" && i + 1 < argc) {
      max_fp_rate = std::atof(argv[++i]);
    }
  }

  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::DedupReport r = tryops::run_dedup_wire(buffer.str());

  const bool gate_ok = r.theoretical_fp_rate <= max_fp_rate;

  std::cout << "{";
  std::cout << "\"total\":" << r.total << ",";
  std::cout << "\"admitted\":" << r.admitted << ",";
  std::cout << "\"rejected_dupe\":" << r.rejected_dupe << ",";
  std::cout << "\"bits\":" << r.bits << ",";
  std::cout << "\"hashes\":" << r.hashes << ",";
  std::cout << "\"set_bits\":" << r.set_bits << ",";
  std::cout << "\"fill_ratio\":" << json_double(r.fill_ratio) << ",";
  std::cout << "\"theoretical_fp_rate\":" << json_double(r.theoretical_fp_rate) << ",";
  std::cout << "\"max_fp_rate\":" << json_double(max_fp_rate) << ",";
  std::cout << "\"gate_ok\":" << (gate_ok ? "true" : "false");
  std::cout << "}\n";
  return gate_ok ? 0 : 2;
}
