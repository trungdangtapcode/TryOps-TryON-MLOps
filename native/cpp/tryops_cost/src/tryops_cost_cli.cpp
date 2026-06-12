// Reads a usage wire stream and emits a per-tenant / per-model cost + carbon
// chargeback report as JSON. Exit 0 always (reporting tool).
#include "tryops_cost.hpp"

#include <iostream>
#include <sstream>
#include <string>

namespace {

std::string usd(double v) {
  std::ostringstream out;
  out.setf(std::ios::fixed);
  out.precision(6);
  out << v;
  return out.str();
}

void emit_bucket(std::ostream& os, const std::string& name,
                 const tryops::CostBucket& b) {
  os << "\"" << name << "\":{";
  os << "\"requests\":" << b.requests << ",";
  os << "\"in_tokens\":" << b.in_tokens << ",";
  os << "\"out_tokens\":" << b.out_tokens << ",";
  os << "\"token_usd\":" << usd(b.token_usd) << ",";
  os << "\"gpu_usd\":" << usd(b.gpu_usd) << ",";
  os << "\"energy_usd\":" << usd(b.energy_usd) << ",";
  os << "\"total_usd\":" << usd(b.total_usd) << ",";
  os << "\"carbon_g\":" << usd(b.carbon_g);
  os << "}";
}

void emit_map(std::ostream& os, const std::string& label,
              const std::map<std::string, tryops::CostBucket>& m) {
  os << "\"" << label << "\":{";
  bool first = true;
  for (const auto& kv : m) {
    if (!first) os << ",";
    first = false;
    emit_bucket(os, kv.first, kv.second);
  }
  os << "}";
}

}  // namespace

int main() {
  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::CostReport r = tryops::run_cost_wire(buffer.str());

  std::cout << "{";
  emit_map(std::cout, "per_tenant", r.per_tenant);
  std::cout << ",";
  emit_map(std::cout, "per_model", r.per_model);
  std::cout << ",";
  emit_bucket(std::cout, "total", r.total);
  std::cout << "}\n";
  return 0;
}
