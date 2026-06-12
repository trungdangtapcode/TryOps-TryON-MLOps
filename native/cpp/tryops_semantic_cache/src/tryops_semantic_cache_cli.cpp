#include "tryops_semantic_cache.hpp"

#include <iostream>

int main() {
  const auto payload = tryops::semantic_cache::read_key_values(std::cin);
  const std::string query = tryops::semantic_cache::get_string(payload, "query");
  const double threshold = tryops::semantic_cache::get_double(payload, "threshold", 0.72);
  const auto entries = tryops::semantic_cache::parse_entries(payload);
  const auto result = tryops::semantic_cache::lookup(query, threshold, entries);
  std::cout << tryops::semantic_cache::render_json(result);
  return 0;
}
