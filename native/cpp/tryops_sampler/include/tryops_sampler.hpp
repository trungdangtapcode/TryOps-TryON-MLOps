// TryOps native trace sampler.
//
// Keeps a bounded, statistically representative sample of a high-volume trace
// stream so observability stays affordable. Two modes:
//   * reservoir (Algorithm R): every item has equal probability k/n of being
//     kept, in a single pass with O(k) memory and no prior knowledge of n.
//   * priority: a weighted/"always keep errors" variant that forces flagged
//     spans (errors, slow requests) into the sample while filling the remainder
//     uniformly.
// A shared deterministic xorshift64 RNG makes the selection reproducible and
// lets the C++ engine and the Python reference agree bit-for-bit given a seed.
#ifndef TRYOPS_SAMPLER_HPP
#define TRYOPS_SAMPLER_HPP

#include <cstdint>
#include <string>
#include <vector>

namespace tryops {

// Deterministic xorshift64* PRNG (reproduced exactly in Python).
class Xorshift64 {
 public:
  explicit Xorshift64(std::uint64_t seed) : state_(seed ? seed : 0x9E3779B97F4A7C15ULL) {}
  std::uint64_t next() {
    std::uint64_t x = state_;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    state_ = x;
    return x * 0x2545F4914F6CDD1DULL;
  }
  // uniform integer in [0, bound)
  std::uint64_t below(std::uint64_t bound) { return bound ? next() % bound : 0; }

 private:
  std::uint64_t state_;
};

struct TraceItem {
  std::string id;
  bool priority = false;  // force-keep (e.g. error/slow span)
};

struct SamplerReport {
  std::int64_t observed = 0;
  std::int64_t priority_seen = 0;
  std::int64_t priority_kept = 0;
  std::size_t capacity = 0;
  std::vector<std::string> sample;  // kept item ids, in reservoir order
};

// Reservoir Algorithm R over the items, using the given seed.
SamplerReport reservoir_sample(const std::vector<TraceItem>& items,
                               std::size_t capacity, std::uint64_t seed);

// Priority-preserving sample: all priority items are kept (up to capacity),
// remaining slots filled by reservoir over the non-priority items.
SamplerReport priority_sample(const std::vector<TraceItem>& items,
                              std::size_t capacity, std::uint64_t seed);

// Parse and run a wire stream:
//   capacity=...  seed=...  mode=reservoir|priority
//   item=id=<s>;priority=<0|1>
SamplerReport run_sampler_wire(const std::string& text);

}  // namespace tryops

#endif  // TRYOPS_SAMPLER_HPP
