// tryops_experiment_router: native online-experiment routing engine.
//
// Protocol: read key=value lines from stdin, emit one JSON object on stdout.
// The engine keeps the hot decision path outside Python: stable A/B bucketing,
// guardrail eligibility, and UCB-style bandit allocation.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Variant {
  std::string name;
  std::string adapter;
  double allocation_percent = 0.0;
  double impressions = 0.0;
  double rewards = 0.0;
  double guardrail_block_rate = 0.0;
  double latency_p95_ms = 0.0;
  double error_rate = 0.0;
  bool eligible = true;
  double reward_rate = 0.0;
  double ucb_score = 0.0;
  double route_weight = 0.0;
  double traffic_percent = 0.0;
  std::vector<std::string> violations;
};

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
        out << ch;
        break;
    }
  }
  return out.str();
}

std::map<std::string, std::string> read_payload() {
  std::map<std::string, std::string> values;
  std::string line;
  while (std::getline(std::cin, line)) {
    const auto sep = line.find('=');
    if (sep == std::string::npos) {
      continue;
    }
    values[line.substr(0, sep)] = line.substr(sep + 1);
  }
  return values;
}

std::string get_string(const std::map<std::string, std::string>& payload,
                       const std::string& key,
                       const std::string& fallback = "") {
  const auto found = payload.find(key);
  return found == payload.end() ? fallback : found->second;
}

int get_int(const std::map<std::string, std::string>& payload,
            const std::string& key,
            int fallback = 0) {
  const auto found = payload.find(key);
  if (found == payload.end()) {
    return fallback;
  }
  try {
    return std::stoi(found->second);
  } catch (...) {
    return fallback;
  }
}

double get_double(const std::map<std::string, std::string>& payload,
                  const std::string& key,
                  double fallback = 0.0) {
  const auto found = payload.find(key);
  if (found == payload.end()) {
    return fallback;
  }
  try {
    return std::stod(found->second);
  } catch (...) {
    return fallback;
  }
}

std::uint64_t fnv1a64(const std::string& value) {
  std::uint64_t hash = 1469598103934665603ULL;
  for (const unsigned char ch : value) {
    hash ^= static_cast<std::uint64_t>(ch);
    hash *= 1099511628211ULL;
  }
  return hash;
}

double stable_bucket(const std::string& key) {
  const std::uint64_t million = 1000000ULL;
  return static_cast<double>(fnv1a64(key) % million) / 10000.0;
}

std::vector<Variant> parse_variants(const std::map<std::string, std::string>& payload) {
  const int count = get_int(payload, "variant_count", 0);
  std::vector<Variant> variants;
  variants.reserve(static_cast<std::size_t>(std::max(0, count)));
  for (int i = 0; i < count; ++i) {
    const std::string prefix = "variant." + std::to_string(i) + ".";
    Variant variant;
    variant.name = get_string(payload, prefix + "name");
    variant.adapter = get_string(payload, prefix + "adapter", variant.name);
    variant.allocation_percent = get_double(payload, prefix + "allocation_percent", 0.0);
    variant.impressions = get_double(payload, prefix + "impressions", 0.0);
    variant.rewards = get_double(payload, prefix + "rewards", 0.0);
    variant.guardrail_block_rate = get_double(payload, prefix + "guardrail_block_rate", 0.0);
    variant.latency_p95_ms = get_double(payload, prefix + "latency_p95_ms", 0.0);
    variant.error_rate = get_double(payload, prefix + "error_rate", 0.0);
    if (!variant.name.empty()) {
      variants.push_back(variant);
    }
  }
  return variants;
}

void apply_guardrails(std::vector<Variant>& variants,
                      double max_block_rate,
                      double max_latency_p95_ms,
                      double max_error_rate) {
  for (auto& variant : variants) {
    if (variant.guardrail_block_rate > max_block_rate) {
      variant.eligible = false;
      variant.violations.push_back("guardrail_block_rate");
    }
    if (variant.latency_p95_ms > max_latency_p95_ms) {
      variant.eligible = false;
      variant.violations.push_back("latency_p95_ms");
    }
    if (variant.error_rate > max_error_rate) {
      variant.eligible = false;
      variant.violations.push_back("error_rate");
    }
    if (variant.impressions > 0.0) {
      variant.reward_rate = variant.rewards / variant.impressions;
    }
  }
}

int eligible_count(const std::vector<Variant>& variants) {
  int count = 0;
  for (const auto& variant : variants) {
    if (variant.eligible) {
      ++count;
    }
  }
  return count;
}

double total_impressions(const std::vector<Variant>& variants) {
  double total = 0.0;
  for (const auto& variant : variants) {
    total += std::max(0.0, variant.impressions);
  }
  return std::max(1.0, total);
}

void assign_weights(std::vector<Variant>& variants, const std::string& mode, double holdback_percent) {
  double total_weight = 0.0;
  const int eligibles = eligible_count(variants);
  if (eligibles == 0) {
    throw std::runtime_error("no eligible variants after guardrail filtering");
  }
  if (mode == "ab") {
    for (auto& variant : variants) {
      if (variant.eligible) {
        variant.route_weight = std::max(0.0, variant.allocation_percent);
        total_weight += variant.route_weight;
      }
    }
    if (total_weight <= 0.0) {
      for (auto& variant : variants) {
        if (variant.eligible) {
          variant.route_weight = 1.0;
          total_weight += 1.0;
        }
      }
    }
  } else if (mode == "bandit") {
    const double total = total_impressions(variants);
    for (auto& variant : variants) {
      if (!variant.eligible) {
        continue;
      }
      if (variant.impressions <= 0.0) {
        variant.ucb_score = 2.0;
      } else {
        variant.ucb_score =
            variant.reward_rate + std::sqrt((2.0 * std::log(std::max(2.0, total))) / variant.impressions);
      }
      variant.route_weight = std::max(0.000001, variant.ucb_score);
      total_weight += variant.route_weight;
    }
  } else {
    throw std::runtime_error("mode must be ab or bandit");
  }
  const double routed_percent = std::max(0.0, 100.0 - holdback_percent);
  for (auto& variant : variants) {
    if (variant.eligible && total_weight > 0.0) {
      variant.traffic_percent = (variant.route_weight / total_weight) * routed_percent;
    }
  }
}

const Variant* choose_variant(const std::vector<Variant>& variants, double routed_bucket) {
  double cumulative = 0.0;
  const Variant* fallback = nullptr;
  for (const auto& variant : variants) {
    if (!variant.eligible) {
      continue;
    }
    fallback = &variant;
    cumulative += variant.traffic_percent;
    if (routed_bucket < cumulative) {
      return &variant;
    }
  }
  return fallback;
}

void print_string_array(const std::vector<std::string>& values) {
  std::cout << "[";
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i > 0) {
      std::cout << ",";
    }
    std::cout << "\"" << json_escape(values[i]) << "\"";
  }
  std::cout << "]";
}

void print_json(const std::map<std::string, std::string>& payload,
                const std::vector<Variant>& variants,
                const Variant* selected,
                double bucket,
                double routed_bucket,
                bool holdback,
                double max_block_rate,
                double max_latency_p95_ms,
                double max_error_rate) {
  const std::string mode = get_string(payload, "mode", "ab");
  const std::string request_id = get_string(payload, "request_id");
  const std::string experiment_id = get_string(payload, "experiment_id", "tryops-experiment");
  const std::string holdback_alias = get_string(payload, "holdback_alias", "champion");
  const std::string holdback_adapter = get_string(payload, "holdback_adapter", "tryops-rule-baseline");
  const std::string selected_name = holdback ? holdback_alias : (selected ? selected->name : "");
  const std::string selected_adapter = holdback ? holdback_adapter : (selected ? selected->adapter : "");
  const std::string reason = holdback ? "holdback" : (mode == "bandit" ? "bandit_ucb_guarded" : "ab_bucket_guarded");

  std::cout << std::fixed << std::setprecision(6);
  std::cout << "{";
  std::cout << "\"schema_version\":\"tryops.native_experiment_router.v1\",";
  std::cout << "\"engine\":{\"name\":\"tryops_experiment_router\",\"language\":\"c++\",\"version\":\"0.1.0\"},";
  std::cout << "\"mode\":\"" << json_escape(mode) << "\",";
  std::cout << "\"experiment_id\":\"" << json_escape(experiment_id) << "\",";
  std::cout << "\"request_id\":\"" << json_escape(request_id) << "\",";
  std::cout << "\"bucket\":" << bucket << ",";
  std::cout << "\"routed_bucket\":" << routed_bucket << ",";
  std::cout << "\"holdback\":" << (holdback ? "true" : "false") << ",";
  std::cout << "\"selected\":{\"variant\":\"" << json_escape(selected_name) << "\",";
  std::cout << "\"adapter\":\"" << json_escape(selected_adapter) << "\",";
  std::cout << "\"reason\":\"" << json_escape(reason) << "\"},";
  std::cout << "\"guardrail_thresholds\":{";
  std::cout << "\"max_block_rate\":" << max_block_rate << ",";
  std::cout << "\"max_latency_p95_ms\":" << max_latency_p95_ms << ",";
  std::cout << "\"max_error_rate\":" << max_error_rate << "},";
  std::cout << "\"variants\":[";
  for (std::size_t i = 0; i < variants.size(); ++i) {
    if (i > 0) {
      std::cout << ",";
    }
    const auto& v = variants[i];
    std::cout << "{";
    std::cout << "\"name\":\"" << json_escape(v.name) << "\",";
    std::cout << "\"adapter\":\"" << json_escape(v.adapter) << "\",";
    std::cout << "\"eligible\":" << (v.eligible ? "true" : "false") << ",";
    std::cout << "\"violations\":";
    print_string_array(v.violations);
    std::cout << ",";
    std::cout << "\"ab_allocation_percent\":" << v.allocation_percent << ",";
    std::cout << "\"traffic_percent\":" << v.traffic_percent << ",";
    std::cout << "\"impressions\":" << v.impressions << ",";
    std::cout << "\"rewards\":" << v.rewards << ",";
    std::cout << "\"reward_rate\":" << v.reward_rate << ",";
    std::cout << "\"ucb_score\":" << v.ucb_score << ",";
    std::cout << "\"guardrail_block_rate\":" << v.guardrail_block_rate << ",";
    std::cout << "\"latency_p95_ms\":" << v.latency_p95_ms << ",";
    std::cout << "\"error_rate\":" << v.error_rate;
    std::cout << "}";
  }
  std::cout << "]}";
  std::cout << "\n";
}

}  // namespace

int main() {
  try {
    auto payload = read_payload();
    const std::string experiment_id = get_string(payload, "experiment_id", "tryops-experiment");
    const std::string request_id = get_string(payload, "request_id");
    const double holdback_percent = std::clamp(get_double(payload, "holdback_percent", 0.0), 0.0, 95.0);
    const double max_block_rate = get_double(payload, "guardrail.max_block_rate", 0.02);
    const double max_latency_p95_ms = get_double(payload, "guardrail.max_latency_p95_ms", 500.0);
    const double max_error_rate = get_double(payload, "guardrail.max_error_rate", 0.01);
    auto variants = parse_variants(payload);
    if (request_id.empty()) {
      throw std::runtime_error("missing required key request_id");
    }
    if (variants.empty()) {
      throw std::runtime_error("variant_count produced no variants");
    }
    apply_guardrails(variants, max_block_rate, max_latency_p95_ms, max_error_rate);
    assign_weights(variants, get_string(payload, "mode", "ab"), holdback_percent);
    const double bucket = stable_bucket(experiment_id + "::" + request_id);
    const bool holdback = bucket < holdback_percent;
    double routed_bucket = 0.0;
    const Variant* selected = nullptr;
    if (!holdback) {
      routed_bucket = bucket - holdback_percent;
      selected = choose_variant(variants, routed_bucket);
    }
    print_json(payload, variants, selected, bucket, routed_bucket, holdback,
               max_block_rate, max_latency_p95_ms, max_error_rate);
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
