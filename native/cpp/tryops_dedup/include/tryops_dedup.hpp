// TryOps native idempotency-key dedup via a Bloom filter.
//
// At the production boundary a request carries an idempotency key; replays must
// be rejected without a round-trip to a database. A Bloom filter answers
// "definitely new" vs "possibly seen" in O(k) with a fixed, tiny memory budget
// and zero false negatives (a real duplicate is never admitted twice). The
// false-positive rate is tuned from the expected item count and target rate.
#ifndef TRYOPS_DEDUP_HPP
#define TRYOPS_DEDUP_HPP

#include <cstdint>
#include <string>
#include <vector>

namespace tryops {

struct DedupConfig {
  std::uint64_t expected_items = 10000;  // n
  double target_fp_rate = 0.01;          // p
};

struct DedupReport {
  std::uint64_t total = 0;
  std::uint64_t admitted = 0;        // first-seen keys
  std::uint64_t rejected_dupe = 0;   // possibly-seen keys
  std::uint64_t bits = 0;            // m
  std::uint32_t hashes = 0;          // k
  std::uint64_t set_bits = 0;        // population count
  double fill_ratio = 0.0;           // set_bits / m
  double theoretical_fp_rate = 0.0;  // (1 - e^{-kn/m})^k at current load
};

class BloomFilter {
 public:
  BloomFilter(std::uint64_t expected_items, double target_fp_rate);

  // Returns true if the key was newly inserted (first-seen), false if it was
  // possibly already present (treated as a duplicate).
  bool insert_if_absent(const std::string& key);

  bool maybe_contains(const std::string& key) const;

  std::uint64_t bits() const { return bits_; }
  std::uint32_t hashes() const { return hashes_; }
  std::uint64_t set_bits() const;

 private:
  void positions(const std::string& key, std::vector<std::uint64_t>& out) const;

  std::uint64_t bits_;
  std::uint32_t hashes_;
  std::vector<std::uint64_t> words_;  // bitset packed into 64-bit words
};

// Optimal sizing helpers (Bloom-filter math).
std::uint64_t optimal_bits(std::uint64_t n, double p);
std::uint32_t optimal_hashes(std::uint64_t m, std::uint64_t n);

// Run a newline-delimited key stream (after an optional config header) and
// report dedup stats.
DedupReport run_dedup_wire(const std::string& text);

}  // namespace tryops

#endif  // TRYOPS_DEDUP_HPP
