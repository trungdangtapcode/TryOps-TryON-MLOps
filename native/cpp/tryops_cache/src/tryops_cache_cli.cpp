// Reads a cache event wire stream on stdin, simulates the LRU+TTL cache, prints
// a JSON report. Exit 0 if the hit rate meets --min-hit-rate, else 2.
#include "tryops_cache.hpp"

#include <iostream>
#include <sstream>
#include <string>

int main(int argc, char** argv) {
  double min_hit_rate = 0.0;
  for (int i = 1; i < argc; ++i) {
    if (std::string(argv[i]) == "--min-hit-rate" && i + 1 < argc) {
      min_hit_rate = std::atof(argv[++i]);
    }
  }

  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::CacheReport r = tryops::run_cache_wire(buffer.str());

  std::ostringstream hr;
  hr.setf(std::ios::fixed);
  hr.precision(6);
  hr << r.hit_rate;

  const bool gate_ok = r.hit_rate >= min_hit_rate;

  std::cout << "{";
  std::cout << "\"total\":" << r.total << ",";
  std::cout << "\"hits\":" << r.hits << ",";
  std::cout << "\"misses\":" << r.misses << ",";
  std::cout << "\"evictions\":" << r.evictions << ",";
  std::cout << "\"expirations\":" << r.expirations << ",";
  std::cout << "\"final_size\":" << r.final_size << ",";
  std::cout << "\"hit_rate\":" << hr.str() << ",";
  std::cout << "\"min_hit_rate\":" << min_hit_rate << ",";
  std::cout << "\"gate_ok\":" << (gate_ok ? "true" : "false");
  std::cout << "}\n";
  return gate_ok ? 0 : 2;
}
