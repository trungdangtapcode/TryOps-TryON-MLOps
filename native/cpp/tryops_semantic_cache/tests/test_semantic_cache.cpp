#include "tryops_semantic_cache.hpp"

#include <cassert>
#include <cmath>
#include <sstream>
#include <string>

namespace {

void assert_contains(const std::string& body, const std::string& expected) {
  assert(body.find(expected) != std::string::npos);
}

}  // namespace

int main() {
  std::istringstream input(
      "query=blue striped shirt\n"
      "threshold=0.5\n"
      "entry_count=2\n"
      "entry.0.id=shirt-blue\n"
      "entry.0.prompt=a blue striped shirt\n"
      "entry.0.input_tokens=11\n"
      "entry.0.output_tokens=22\n"
      "entry.0.cost_usd=0.03\n"
      "entry.0.energy_wh=0.4\n"
      "entry.1.id=red-dress\n"
      "entry.1.prompt=a red dress\n");

  const auto payload = tryops::semantic_cache::read_key_values(input);
  const auto entries = tryops::semantic_cache::parse_entries(payload);
  assert(entries.size() == 2);

  const auto result = tryops::semantic_cache::lookup(
      tryops::semantic_cache::get_string(payload, "query"),
      tryops::semantic_cache::get_double(payload, "threshold", 0.72),
      entries);
  assert(result.candidates.size() == 2);
  assert(result.candidates[0].entry.id == "shirt-blue");
  assert(result.candidates[0].score > result.candidates[1].score);
  assert(std::fabs(tryops::semantic_cache::cosine_similarity(
                       tryops::semantic_cache::embedding("same text"),
                       tryops::semantic_cache::embedding("same text")) -
                   1.0) < 0.000001);

  const auto body = tryops::semantic_cache::render_json(result);
  assert_contains(body, "\"schema_version\":\"tryops.native_semantic_cache.v1\"");
  assert_contains(body, "\"hit\":true");
  assert_contains(body, "\"matched_entry_id\":\"shirt-blue\"");
  assert_contains(body, "\"source\":\"native_cpp_cli\"");
  return 0;
}
