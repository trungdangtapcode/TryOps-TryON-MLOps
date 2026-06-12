#pragma once

#include <istream>
#include <map>
#include <string>
#include <vector>

namespace tryops::semantic_cache {

using Payload = std::map<std::string, std::string>;
using SparseVector = std::map<std::string, double>;

struct Entry {
  std::string id;
  std::string prompt;
  double input_tokens = 0.0;
  double output_tokens = 0.0;
  double cost_usd = 0.0;
  double energy_wh = 0.0;
};

struct Candidate {
  Entry entry;
  double score = 0.0;
};

struct LookupResult {
  std::string query;
  double threshold = 0.72;
  std::vector<Entry> entries;
  std::vector<Candidate> candidates;
};

Payload read_key_values(std::istream& input);
std::string get_string(const Payload& payload, const std::string& key);
double get_double(const Payload& payload, const std::string& key, double default_value);
int get_int(const Payload& payload, const std::string& key, int default_value);

std::vector<std::string> tokenize(const std::string& text);
SparseVector embedding(const std::string& text);
double cosine_similarity(const SparseVector& left, const SparseVector& right);

std::vector<Entry> parse_entries(const Payload& payload);
LookupResult lookup(const std::string& query, double threshold, const std::vector<Entry>& entries);
std::string render_json(const LookupResult& result);

}  // namespace tryops::semantic_cache
