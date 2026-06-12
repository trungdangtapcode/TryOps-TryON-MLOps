// tryops_experiment_stats: native online-experiment analysis engine.
//
// Protocol: read key=value lines from stdin, emit one JSON object on stdout.
// Computes holdback uplift confidence intervals and Wald-style sequential
// likelihood-ratio decisions without a Python statistics dependency.

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Arm {
  std::string name;
  double impressions = 0.0;
  double rewards = 0.0;
  double rate = 0.0;
  double uplift_absolute = 0.0;
  double uplift_relative = 0.0;
  double ci_lo = 0.0;
  double ci_hi = 0.0;
  bool ci_excludes_zero = false;
  double p0 = 0.0;
  double p1 = 0.0;
  double log_likelihood_ratio = 0.0;
  double lower_boundary = 0.0;
  double upper_boundary = 0.0;
  std::string sequential_verdict = "continue";
  bool early_stop = false;
  std::string stop_reason = "needs_more_data";
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

double clamp_probability(double value) {
  return std::clamp(value, 0.000001, 0.999999);
}

double rate(double rewards, double impressions) {
  if (impressions <= 0.0) {
    return 0.0;
  }
  return rewards / impressions;
}

double z_for_confidence(double confidence) {
  if (std::fabs(confidence - 0.90) < 0.000001) {
    return 1.644854;
  }
  if (std::fabs(confidence - 0.99) < 0.000001) {
    return 2.575829;
  }
  return 1.959964;
}

std::vector<Arm> parse_variants(const std::map<std::string, std::string>& payload) {
  const int count = get_int(payload, "variant_count", 0);
  std::vector<Arm> variants;
  variants.reserve(static_cast<std::size_t>(std::max(0, count)));
  for (int i = 0; i < count; ++i) {
    const std::string prefix = "variant." + std::to_string(i) + ".";
    Arm arm;
    arm.name = get_string(payload, prefix + "name");
    arm.impressions = get_double(payload, prefix + "impressions", 0.0);
    arm.rewards = get_double(payload, prefix + "rewards", 0.0);
    if (!arm.name.empty()) {
      variants.push_back(arm);
    }
  }
  return variants;
}

void analyze_arm(Arm& arm,
                 const Arm& holdback,
                 double confidence,
                 double alpha,
                 double beta,
                 double min_detectable_effect,
                 double min_sample_size) {
  if (arm.impressions <= 0.0) {
    throw std::runtime_error("variant impressions must be positive");
  }
  arm.rate = rate(arm.rewards, arm.impressions);
  arm.uplift_absolute = arm.rate - holdback.rate;
  if (holdback.rate > 0.0) {
    arm.uplift_relative = arm.uplift_absolute / holdback.rate;
  }

  const double adjusted_arm_n = arm.impressions + 2.0;
  const double adjusted_holdback_n = holdback.impressions + 2.0;
  const double adjusted_arm_p = (arm.rewards + 1.0) / adjusted_arm_n;
  const double adjusted_holdback_p = (holdback.rewards + 1.0) / adjusted_holdback_n;
  const double adjusted_diff = adjusted_arm_p - adjusted_holdback_p;
  const double se = std::sqrt(
      (adjusted_arm_p * (1.0 - adjusted_arm_p) / adjusted_arm_n) +
      (adjusted_holdback_p * (1.0 - adjusted_holdback_p) / adjusted_holdback_n));
  const double margin = z_for_confidence(confidence) * se;
  arm.ci_lo = adjusted_diff - margin;
  arm.ci_hi = adjusted_diff + margin;
  arm.ci_excludes_zero = (arm.ci_lo > 0.0) || (arm.ci_hi < 0.0);

  arm.p0 = clamp_probability(holdback.rate);
  arm.p1 = clamp_probability(holdback.rate + min_detectable_effect);
  arm.lower_boundary = std::log(beta / (1.0 - alpha));
  arm.upper_boundary = std::log((1.0 - beta) / alpha);
  arm.log_likelihood_ratio =
      arm.rewards * std::log(arm.p1 / arm.p0) +
      (arm.impressions - arm.rewards) * std::log((1.0 - arm.p1) / (1.0 - arm.p0));

  if (arm.impressions < min_sample_size || holdback.impressions < min_sample_size) {
    arm.sequential_verdict = "continue";
    arm.early_stop = false;
    arm.stop_reason = "minimum_sample_not_met";
  } else if (arm.log_likelihood_ratio >= arm.upper_boundary) {
    arm.sequential_verdict = "accept_variant";
    arm.early_stop = true;
    arm.stop_reason = "sprt_upper_boundary_crossed";
  } else if (arm.log_likelihood_ratio <= arm.lower_boundary) {
    arm.sequential_verdict = "accept_holdback";
    arm.early_stop = true;
    arm.stop_reason = "sprt_lower_boundary_crossed";
  } else {
    arm.sequential_verdict = "continue";
    arm.early_stop = false;
    arm.stop_reason = "inside_sprt_boundaries";
  }
}

void print_arm(const Arm& arm, double confidence) {
  std::cout << "{";
  std::cout << "\"name\":\"" << json_escape(arm.name) << "\",";
  std::cout << "\"impressions\":" << arm.impressions << ",";
  std::cout << "\"rewards\":" << arm.rewards << ",";
  std::cout << "\"rate\":" << arm.rate << ",";
  std::cout << "\"uplift_absolute\":" << arm.uplift_absolute << ",";
  std::cout << "\"uplift_relative\":" << arm.uplift_relative << ",";
  std::cout << "\"uplift_ci\":{";
  std::cout << "\"method\":\"agresti_caffo_adjusted_difference\",";
  std::cout << "\"confidence\":" << confidence << ",";
  std::cout << "\"lo\":" << arm.ci_lo << ",";
  std::cout << "\"hi\":" << arm.ci_hi << ",";
  std::cout << "\"excludes_zero\":" << (arm.ci_excludes_zero ? "true" : "false") << "},";
  std::cout << "\"sequential\":{";
  std::cout << "\"method\":\"wald_sprt_binomial_vs_holdback_rate\",";
  std::cout << "\"p0\":" << arm.p0 << ",";
  std::cout << "\"p1\":" << arm.p1 << ",";
  std::cout << "\"log_likelihood_ratio\":" << arm.log_likelihood_ratio << ",";
  std::cout << "\"lower_boundary\":" << arm.lower_boundary << ",";
  std::cout << "\"upper_boundary\":" << arm.upper_boundary << ",";
  std::cout << "\"verdict\":\"" << arm.sequential_verdict << "\",";
  std::cout << "\"early_stop\":" << (arm.early_stop ? "true" : "false") << ",";
  std::cout << "\"reason\":\"" << arm.stop_reason << "\"}";
  std::cout << "}";
}

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    const std::string experiment_id = get_string(payload, "experiment_id", "tryops-experiment");
    const double confidence = get_double(payload, "confidence", 0.95);
    const double alpha = get_double(payload, "alpha", 0.05);
    const double beta = get_double(payload, "beta", 0.20);
    const double min_detectable_effect = get_double(payload, "min_detectable_effect", 0.05);
    const double min_sample_size = get_double(payload, "min_sample_size", 100.0);

    Arm holdback;
    holdback.name = get_string(payload, "holdback.name", "holdback");
    holdback.impressions = get_double(payload, "holdback.impressions", 0.0);
    holdback.rewards = get_double(payload, "holdback.rewards", 0.0);
    if (holdback.impressions <= 0.0) {
      throw std::runtime_error("holdback.impressions must be positive");
    }
    holdback.rate = rate(holdback.rewards, holdback.impressions);

    auto variants = parse_variants(payload);
    if (variants.empty()) {
      throw std::runtime_error("variant_count produced no variants");
    }
    for (auto& variant : variants) {
      analyze_arm(variant, holdback, confidence, alpha, beta, min_detectable_effect, min_sample_size);
    }

    const Arm* best = nullptr;
    for (const auto& variant : variants) {
      if (best == nullptr || variant.uplift_absolute > best->uplift_absolute) {
        best = &variant;
      }
    }

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "{";
    std::cout << "\"schema_version\":\"tryops.native_experiment_stats.v1\",";
    std::cout << "\"engine\":{\"name\":\"tryops_experiment_stats\",\"language\":\"c++\",\"version\":\"0.1.0\"},";
    std::cout << "\"experiment_id\":\"" << json_escape(experiment_id) << "\",";
    std::cout << "\"confidence\":" << confidence << ",";
    std::cout << "\"alpha\":" << alpha << ",";
    std::cout << "\"beta\":" << beta << ",";
    std::cout << "\"min_detectable_effect\":" << min_detectable_effect << ",";
    std::cout << "\"min_sample_size\":" << min_sample_size << ",";
    std::cout << "\"holdback\":{";
    std::cout << "\"name\":\"" << json_escape(holdback.name) << "\",";
    std::cout << "\"impressions\":" << holdback.impressions << ",";
    std::cout << "\"rewards\":" << holdback.rewards << ",";
    std::cout << "\"rate\":" << holdback.rate << "},";
    std::cout << "\"variants\":[";
    for (std::size_t i = 0; i < variants.size(); ++i) {
      if (i > 0) {
        std::cout << ",";
      }
      print_arm(variants[i], confidence);
    }
    std::cout << "],";
    std::cout << "\"best_variant\":\"" << json_escape(best ? best->name : "") << "\"";
    std::cout << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
