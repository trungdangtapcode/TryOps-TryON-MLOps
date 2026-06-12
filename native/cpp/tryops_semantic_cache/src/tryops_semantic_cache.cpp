#include "tryops_semantic_cache.hpp"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <iomanip>
#include <sstream>

namespace tryops::semantic_cache {
namespace {

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    switch (ch) {
      case '\\':
        out << "\\\\";
        break;
      case '"':
        out << "\\\"";
        break;
      case '\n':
        out << "\\n";
        break;
      case '\r':
        out << "\\r";
        break;
      case '\t':
        out << "\\t";
        break;
      default:
        if (static_cast<unsigned char>(ch) < 0x20) {
          out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
              << static_cast<int>(static_cast<unsigned char>(ch)) << std::dec;
        } else {
          out << ch;
        }
        break;
    }
  }
  return out.str();
}

std::string lower_ascii(const std::string& value) {
  std::string out;
  out.reserve(value.size());
  for (const unsigned char ch : value) {
    out.push_back(static_cast<char>(std::tolower(ch)));
  }
  return out;
}

}  // namespace

Payload read_key_values(std::istream& input) {
  Payload payload;
  std::string line;
  while (std::getline(input, line)) {
    const auto separator = line.find('=');
    if (separator == std::string::npos) {
      continue;
    }
    payload[line.substr(0, separator)] = line.substr(separator + 1);
  }
  return payload;
}

std::string get_string(const Payload& payload, const std::string& key) {
  const auto found = payload.find(key);
  return found == payload.end() ? "" : found->second;
}

double get_double(const Payload& payload, const std::string& key, double default_value) {
  const auto found = payload.find(key);
  if (found == payload.end()) {
    return default_value;
  }
  try {
    return std::stod(found->second);
  } catch (...) {
    return default_value;
  }
}

int get_int(const Payload& payload, const std::string& key, int default_value) {
  const auto found = payload.find(key);
  if (found == payload.end()) {
    return default_value;
  }
  try {
    return std::stoi(found->second);
  } catch (...) {
    return default_value;
  }
}

std::vector<std::string> tokenize(const std::string& text) {
  std::vector<std::string> tokens;
  std::string current;
  for (const unsigned char ch : lower_ascii(text)) {
    if (std::isalnum(ch)) {
      current.push_back(static_cast<char>(ch));
    } else if (!current.empty()) {
      tokens.push_back(current);
      current.clear();
    }
  }
  if (!current.empty()) {
    tokens.push_back(current);
  }
  return tokens;
}

SparseVector embedding(const std::string& text) {
  SparseVector vector;
  for (const auto& token : tokenize(text)) {
    if (token.size() > 1) {
      vector[token] += 1.0;
    }
  }
  return vector;
}

double cosine_similarity(const SparseVector& left, const SparseVector& right) {
  if (left.empty() || right.empty()) {
    return 0.0;
  }
  double dot = 0.0;
  double left_norm = 0.0;
  double right_norm = 0.0;
  for (const auto& item : left) {
    left_norm += item.second * item.second;
    const auto found = right.find(item.first);
    if (found != right.end()) {
      dot += item.second * found->second;
    }
  }
  for (const auto& item : right) {
    right_norm += item.second * item.second;
  }
  if (left_norm <= 0.0 || right_norm <= 0.0) {
    return 0.0;
  }
  return dot / (std::sqrt(left_norm) * std::sqrt(right_norm));
}

std::vector<Entry> parse_entries(const Payload& payload) {
  std::vector<Entry> entries;
  const int entry_count = std::max(0, get_int(payload, "entry_count", 0));
  entries.reserve(static_cast<std::size_t>(entry_count));
  for (int index = 0; index < entry_count; ++index) {
    const std::string prefix = "entry." + std::to_string(index) + ".";
    Entry entry;
    entry.id = get_string(payload, prefix + "id");
    entry.prompt = get_string(payload, prefix + "prompt");
    entry.input_tokens = get_double(payload, prefix + "input_tokens", 0.0);
    entry.output_tokens = get_double(payload, prefix + "output_tokens", 0.0);
    entry.cost_usd = get_double(payload, prefix + "cost_usd", 0.0);
    entry.energy_wh = get_double(payload, prefix + "energy_wh", 0.0);
    if (!entry.id.empty() && !entry.prompt.empty()) {
      entries.push_back(entry);
    }
  }
  return entries;
}

LookupResult lookup(const std::string& query, double threshold, const std::vector<Entry>& entries) {
  const auto query_embedding = embedding(query);
  std::vector<Candidate> candidates;
  candidates.reserve(entries.size());
  for (const auto& entry : entries) {
    candidates.push_back({entry, cosine_similarity(query_embedding, embedding(entry.prompt))});
  }
  std::sort(candidates.begin(), candidates.end(), [](const Candidate& left, const Candidate& right) {
    if (left.score == right.score) {
      return left.entry.id < right.entry.id;
    }
    return left.score > right.score;
  });

  LookupResult result;
  result.query = query;
  result.threshold = threshold;
  result.entries = entries;
  result.candidates = candidates;
  return result;
}

std::string render_json(const LookupResult& result) {
  const bool hit = !result.candidates.empty() && result.candidates.front().score >= result.threshold;
  const std::string matched_id = hit ? result.candidates.front().entry.id : "";
  const double score = result.candidates.empty() ? 0.0 : result.candidates.front().score;
  const auto query_tokens = tokenize(result.query);

  std::ostringstream out;
  out << std::fixed << std::setprecision(9);
  out << "{";
  out << "\"schema_version\":\"tryops.native_semantic_cache.v1\",";
  out << "\"scanner\":{\"name\":\"tryops_semantic_cache\",\"language\":\"c++\",\"version\":\"0.1.0\"},";
  out << "\"lookup\":{";
  out << "\"hit\":" << (hit ? "true" : "false") << ",";
  out << "\"matched_entry_id\":\"" << json_escape(matched_id) << "\",";
  out << "\"score\":" << score << ",";
  out << "\"threshold\":" << result.threshold << ",";
  out << "\"entry_count\":" << result.entries.size() << ",";
  out << "\"query_token_count\":" << query_tokens.size() << ",";
  out << "\"source\":\"native_cpp_cli\"";
  out << "},";
  out << "\"candidates\":[";
  const std::size_t candidate_limit = std::min<std::size_t>(5, result.candidates.size());
  for (std::size_t index = 0; index < candidate_limit; ++index) {
    if (index > 0) {
      out << ",";
    }
    const auto& candidate = result.candidates[index];
    out << "{";
    out << "\"id\":\"" << json_escape(candidate.entry.id) << "\",";
    out << "\"score\":" << candidate.score << ",";
    out << "\"input_tokens\":" << candidate.entry.input_tokens << ",";
    out << "\"output_tokens\":" << candidate.entry.output_tokens << ",";
    out << "\"cost_usd\":" << candidate.entry.cost_usd << ",";
    out << "\"energy_wh\":" << candidate.entry.energy_wh;
    out << "}";
  }
  out << "]}";
  out << "\n";
  return out.str();
}

}  // namespace tryops::semantic_cache
