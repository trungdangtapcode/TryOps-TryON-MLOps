#include "tryops_hll.hpp"

#include <cmath>
#include <cstdlib>
#include <sstream>

namespace tryops {
namespace {

// FNV-1a then a murmur3 fmix64 finalizer for good avalanche (HLL needs the top
// bits to be well mixed). Both halves are reproduced exactly in Python.
std::uint64_t fnv1a(const std::string& data) {
  std::uint64_t h = 1469598103934665603ULL;
  for (unsigned char c : data) {
    h ^= c;
    h *= 1099511628211ULL;
  }
  return h;
}

std::uint64_t fmix64(std::uint64_t h) {
  h ^= h >> 33;
  h *= 0xff51afd7ed558ccdULL;
  h ^= h >> 33;
  h *= 0xc4ceb9fe1a85ec53ULL;
  h ^= h >> 33;
  return h;
}

int clz64(std::uint64_t x) {
#if defined(__GNUG__)
  return x == 0 ? 64 : __builtin_clzll(x);
#else
  if (x == 0) return 64;
  int n = 0;
  while ((x & (1ULL << 63)) == 0) { x <<= 1; ++n; }
  return n;
#endif
}

double alpha_for(std::uint32_t m) {
  switch (m) {
    case 16: return 0.673;
    case 32: return 0.697;
    case 64: return 0.709;
    default: return 0.7213 / (1.0 + 1.079 / static_cast<double>(m));
  }
}

}  // namespace

std::uint64_t hll_hash(const std::string& value) { return fmix64(fnv1a(value)); }

HyperLogLog::HyperLogLog(int precision) {
  if (precision < 4) precision = 4;
  if (precision > 18) precision = 18;
  precision_ = precision;
  m_ = 1u << precision_;
  reg_.assign(m_, 0);
}

void HyperLogLog::add(const std::string& value) {
  const std::uint64_t h = hll_hash(value);
  const std::uint32_t idx = static_cast<std::uint32_t>(h >> (64 - precision_));
  const std::uint64_t w = h << precision_;  // remaining bits in the high end
  const int rank = (w == 0) ? (64 - precision_ + 1) : (clz64(w) + 1);
  if (static_cast<std::uint8_t>(rank) > reg_[idx]) {
    reg_[idx] = static_cast<std::uint8_t>(rank);
  }
}

double HyperLogLog::estimate() const {
  double sum = 0.0;
  std::uint32_t zeros = 0;
  for (std::uint8_t r : reg_) {
    sum += std::ldexp(1.0, -static_cast<int>(r));  // 2^{-r}
    if (r == 0) ++zeros;
  }
  const double m = static_cast<double>(m_);
  double estimate = alpha_for(m_) * m * m / sum;

  // Small-range correction: linear counting when many registers are still zero.
  if (estimate <= 2.5 * m && zeros != 0) {
    estimate = m * std::log(m / static_cast<double>(zeros));
  }
  return estimate;
}

double HyperLogLog::standard_error() const {
  return 1.04 / std::sqrt(static_cast<double>(m_));
}

HllReport run_hll_wire(const std::string& text) {
  int precision = 14;
  std::vector<std::string> values;
  std::istringstream stream(text);
  std::string line;
  while (std::getline(stream, line)) {
    if (line.empty()) continue;
    const auto sep = line.find('=');
    if (sep != std::string::npos) {
      const std::string key = line.substr(0, sep);
      const std::string value = line.substr(sep + 1);
      if (key == "precision") {
        precision = std::atoi(value.c_str());
        continue;
      }
      if (key == "value") {
        values.push_back(value);
        continue;
      }
    }
    values.push_back(line);
  }

  HyperLogLog hll(precision);
  for (const auto& v : values) hll.add(v);

  HllReport rep;
  rep.precision = hll.precision();
  rep.registers = hll.registers();
  rep.observed = values.size();
  rep.estimate = hll.estimate();
  rep.standard_error = hll.standard_error();
  return rep;
}

}  // namespace tryops
