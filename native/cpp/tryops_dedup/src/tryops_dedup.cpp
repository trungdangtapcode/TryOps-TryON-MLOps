#include "tryops_dedup.hpp"

#include <cmath>
#include <cstdlib>
#include <sstream>

namespace tryops {
namespace {

const double kLn2 = 0.6931471805599453;

std::uint64_t fnv1a(const std::string& data, std::uint64_t basis) {
  std::uint64_t hash = basis;
  for (unsigned char c : data) {
    hash ^= c;
    hash *= 1099511628211ULL;
  }
  return hash;
}

int popcount64(std::uint64_t x) {
#if defined(__GNUG__)
  return __builtin_popcountll(x);
#else
  int n = 0;
  while (x) {
    x &= (x - 1);
    ++n;
  }
  return n;
#endif
}

}  // namespace

std::uint64_t optimal_bits(std::uint64_t n, double p) {
  if (n == 0) {
    n = 1;
  }
  if (p <= 0.0 || p >= 1.0) {
    p = 0.01;
  }
  const double m = -(static_cast<double>(n) * std::log(p)) / (kLn2 * kLn2);
  std::uint64_t bits = static_cast<std::uint64_t>(std::ceil(m));
  return bits < 64 ? 64 : bits;
}

std::uint32_t optimal_hashes(std::uint64_t m, std::uint64_t n) {
  if (n == 0) {
    n = 1;
  }
  const double k = (static_cast<double>(m) / static_cast<double>(n)) * kLn2;
  std::uint32_t hashes = static_cast<std::uint32_t>(std::round(k));
  if (hashes < 1) {
    hashes = 1;
  }
  if (hashes > 32) {
    hashes = 32;
  }
  return hashes;
}

BloomFilter::BloomFilter(std::uint64_t expected_items, double target_fp_rate) {
  bits_ = optimal_bits(expected_items, target_fp_rate);
  hashes_ = optimal_hashes(bits_, expected_items);
  words_.assign((bits_ + 63) / 64, 0ULL);
}

void BloomFilter::positions(const std::string& key,
                            std::vector<std::uint64_t>& out) const {
  // Kirsch-Mitzenmacher double hashing: g_i(x) = h1 + i*h2 mod m.
  const std::uint64_t h1 = fnv1a(key, 1469598103934665603ULL);
  const std::uint64_t h2 = fnv1a(key, 1099511628211ULL) | 1ULL;  // ensure odd
  out.clear();
  out.reserve(hashes_);
  std::uint64_t combined = h1;
  for (std::uint32_t i = 0; i < hashes_; ++i) {
    out.push_back(combined % bits_);
    combined += h2;
  }
}

bool BloomFilter::maybe_contains(const std::string& key) const {
  std::vector<std::uint64_t> pos;
  positions(key, pos);
  for (std::uint64_t p : pos) {
    if ((words_[p / 64] & (1ULL << (p % 64))) == 0) {
      return false;
    }
  }
  return true;
}

bool BloomFilter::insert_if_absent(const std::string& key) {
  std::vector<std::uint64_t> pos;
  positions(key, pos);
  bool was_present = true;
  for (std::uint64_t p : pos) {
    const std::uint64_t mask = 1ULL << (p % 64);
    if ((words_[p / 64] & mask) == 0) {
      was_present = false;
      words_[p / 64] |= mask;
    }
  }
  return !was_present;  // true == newly inserted
}

std::uint64_t BloomFilter::set_bits() const {
  std::uint64_t n = 0;
  for (std::uint64_t w : words_) {
    n += static_cast<std::uint64_t>(popcount64(w));
  }
  return n;
}

DedupReport run_dedup_wire(const std::string& text) {
  DedupConfig config;
  std::vector<std::string> keys;
  std::istringstream stream(text);
  std::string line;
  while (std::getline(stream, line)) {
    if (line.empty()) {
      continue;
    }
    const auto sep = line.find('=');
    if (sep != std::string::npos) {
      const std::string key = line.substr(0, sep);
      const std::string value = line.substr(sep + 1);
      if (key == "expected_items") {
        config.expected_items = static_cast<std::uint64_t>(std::atoll(value.c_str()));
        continue;
      }
      if (key == "target_fp_rate") {
        config.target_fp_rate = std::atof(value.c_str());
        continue;
      }
      if (key == "key") {
        keys.push_back(value);
        continue;
      }
    }
    // bare line is treated as a key
    keys.push_back(line);
  }

  BloomFilter filter(config.expected_items, config.target_fp_rate);
  DedupReport rep;
  rep.bits = filter.bits();
  rep.hashes = filter.hashes();
  for (const auto& k : keys) {
    rep.total += 1;
    if (filter.insert_if_absent(k)) {
      rep.admitted += 1;
    } else {
      rep.rejected_dupe += 1;
    }
  }
  rep.set_bits = filter.set_bits();
  rep.fill_ratio =
      rep.bits > 0 ? static_cast<double>(rep.set_bits) / rep.bits : 0.0;
  // current-load theoretical fp rate: (set_bits/m)^k
  rep.theoretical_fp_rate =
      std::pow(rep.fill_ratio, static_cast<double>(rep.hashes));
  return rep;
}

}  // namespace tryops
