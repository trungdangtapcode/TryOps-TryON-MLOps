// TryOps native HyperLogLog cardinality estimator.
//
// Counts distinct values (unique users, unique prompts, unique error
// fingerprints) in a high-volume stream using O(2^p) bytes of state instead of
// storing every key. Used at the boundary to feed cardinality metrics cheaply.
// Implements the standard HLL estimator with the HLL++ small-range linear-
// counting correction so accuracy holds at low cardinalities too.
#ifndef TRYOPS_HLL_HPP
#define TRYOPS_HLL_HPP

#include <cstdint>
#include <string>
#include <vector>

namespace tryops {

class HyperLogLog {
 public:
  // precision p in [4, 18]; registers m = 2^p. Standard error ~= 1.04/sqrt(m).
  explicit HyperLogLog(int precision = 14);

  void add(const std::string& value);

  // Estimated number of distinct values added.
  double estimate() const;

  int precision() const { return precision_; }
  std::uint32_t registers() const { return m_; }
  double standard_error() const;  // theoretical relative error

 private:
  int precision_;
  std::uint32_t m_;
  std::vector<std::uint8_t> reg_;
};

struct HllReport {
  int precision = 0;
  std::uint32_t registers = 0;
  std::uint64_t observed = 0;     // total items fed
  double estimate = 0.0;          // estimated distinct
  double standard_error = 0.0;    // theoretical relative error
};

// Run a newline stream (optional `precision=` header, then one value per line).
HllReport run_hll_wire(const std::string& text);

// 64-bit hash used by the estimator (exposed for cross-language parity tests).
std::uint64_t hll_hash(const std::string& value);

}  // namespace tryops

#endif  // TRYOPS_HLL_HPP
