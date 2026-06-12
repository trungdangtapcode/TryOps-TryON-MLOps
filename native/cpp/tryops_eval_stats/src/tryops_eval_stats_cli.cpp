// tryops_eval_stats: native percentile-bootstrap confidence interval engine.
//
// Moves the Theme-N statistical hot path (resampling-heavy bootstrap CI) off
// Python and onto the compiled production boundary, matching the platform
// decision that Python is the ML lab layer. Uses a documented deterministic
// splitmix64 RNG so results are reproducible across runs.
//
// Protocol (matching the other tryops native CLIs): read `key=value` lines from
// stdin, emit one JSON object on stdout, emit `{"error":...}` on stderr with a
// non-zero exit code on failure.
//
// Input keys:
//   samples.values=0.2,0.4,0.6,0.8     (comma-separated, >=1 value)
//   n_resamples=2000                   (optional; default 2000)
//   confidence=0.95                    (optional; default 0.95)
//   seed=0                             (optional; default 0)

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    if (ch == '\\' || ch == '"') {
      out << '\\' << ch;
    } else {
      out << ch;
    }
  }
  return out.str();
}

// splitmix64 — small, fast, deterministic.
struct SplitMix64 {
  std::uint64_t state;
  explicit SplitMix64(std::uint64_t seed) : state(seed) {}
  std::uint64_t next() {
    std::uint64_t z = (state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
  }
  std::size_t below(std::size_t n) { return static_cast<std::size_t>(next() % n); }
};

std::vector<double> parse_doubles(const std::string& csv) {
  std::vector<double> values;
  std::stringstream stream(csv);
  std::string token;
  while (std::getline(stream, token, ',')) {
    const auto begin = token.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
      continue;
    }
    const auto end = token.find_last_not_of(" \t\r\n");
    values.push_back(std::stod(token.substr(begin, end - begin + 1)));
  }
  return values;
}

double mean(const std::vector<double>& v) {
  double total = 0.0;
  for (const double x : v) {
    total += x;
  }
  return total / static_cast<double>(v.size());
}

std::unordered_map<std::string, std::string> read_payload() {
  std::unordered_map<std::string, std::string> values;
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

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    if (payload.find("samples.values") == payload.end()) {
      throw std::runtime_error("missing required key samples.values");
    }
    const std::vector<double> values = parse_doubles(payload.at("samples.values"));
    if (values.empty()) {
      throw std::runtime_error("samples.values produced no values");
    }
    std::size_t n_resamples = 2000;
    if (auto it = payload.find("n_resamples"); it != payload.end()) {
      n_resamples = static_cast<std::size_t>(std::stoul(it->second));
    }
    double confidence = 0.95;
    if (auto it = payload.find("confidence"); it != payload.end()) {
      confidence = std::stod(it->second);
    }
    std::uint64_t seed = 0;
    if (auto it = payload.find("seed"); it != payload.end()) {
      seed = static_cast<std::uint64_t>(std::stoull(it->second));
    }

    const double point = mean(values);
    double ci_lo = point;
    double ci_hi = point;
    if (values.size() > 1 && n_resamples > 0) {
      SplitMix64 rng(seed + 0x1234567ULL);
      const std::size_t n = values.size();
      std::vector<double> resampled;
      resampled.reserve(n_resamples);
      for (std::size_t r = 0; r < n_resamples; ++r) {
        double total = 0.0;
        for (std::size_t i = 0; i < n; ++i) {
          total += values[rng.below(n)];
        }
        resampled.push_back(total / static_cast<double>(n));
      }
      std::sort(resampled.begin(), resampled.end());
      const std::size_t lo_idx =
          static_cast<std::size_t>((1.0 - confidence) / 2.0 * static_cast<double>(n_resamples));
      std::size_t hi_idx =
          static_cast<std::size_t>((1.0 + confidence) / 2.0 * static_cast<double>(n_resamples));
      if (hi_idx >= n_resamples) {
        hi_idx = n_resamples - 1;
      }
      ci_lo = resampled[lo_idx];
      ci_hi = resampled[hi_idx];
    }

    std::cout.precision(6);
    std::cout << std::fixed;
    std::cout << "{";
    std::cout << "\"schema_version\":\"tryops.native_eval_stats.v1\",";
    std::cout << "\"point\":" << point << ",";
    std::cout << "\"ci_lo\":" << ci_lo << ",";
    std::cout << "\"ci_hi\":" << ci_hi << ",";
    std::cout << "\"confidence\":" << confidence << ",";
    std::cout << "\"n\":" << values.size() << ",";
    std::cout << "\"n_resamples\":" << n_resamples;
    std::cout << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
