// Reads a value stream (optional `precision=` header, one value per line) and
// prints the HyperLogLog cardinality estimate as JSON. Exit always 0.
#include "tryops_hll.hpp"

#include <iostream>
#include <sstream>
#include <string>

int main() {
  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::HllReport r = tryops::run_hll_wire(buffer.str());

  std::cout.setf(std::ios::fixed);
  std::cout.precision(4);
  std::cout << "{";
  std::cout << "\"precision\":" << r.precision << ",";
  std::cout << "\"registers\":" << r.registers << ",";
  std::cout << "\"observed\":" << r.observed << ",";
  std::cout << "\"estimate\":" << r.estimate << ",";
  std::cout << "\"standard_error\":" << r.standard_error;
  std::cout << "}\n";
  return 0;
}
