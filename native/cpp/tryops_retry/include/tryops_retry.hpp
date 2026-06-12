// TryOps native retry policy engine.
//
// Models the boundary's retry behaviour: exponential backoff with jitter (the
// AWS/SRE "exponential backoff and jitter" pattern) bounded by a retry budget
// (à la gRPC retry throttling) so a wave of failures can't trigger a retry storm
// that amplifies load on an already-struggling backend. Deterministic via a
// shared xorshift64 RNG so jittered delays are reproducible and testable.
#ifndef TRYOPS_RETRY_HPP
#define TRYOPS_RETRY_HPP

#include <cstdint>
#include <string>
#include <vector>

namespace tryops {

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
  // uniform double in [0, 1)
  double unit() { return (next() >> 11) * (1.0 / 9007199254740992.0); }

 private:
  std::uint64_t state_;
};

enum class Jitter { kNone, kFull, kEqual };

struct RetryConfig {
  int max_retries = 3;
  double base_backoff_ms = 50.0;
  double max_backoff_ms = 2000.0;
  Jitter jitter = Jitter::kFull;
  double retry_budget_ratio = 0.2;  // retries capped at this fraction of requests
  std::uint64_t seed = 1;
};

struct RetryRequest {
  // Number of attempts this request needs to succeed (1 = first try). If greater
  // than max_retries+1 the request ultimately fails (retries exhausted).
  int attempts_needed = 1;
};

struct RetryReport {
  std::int64_t requests = 0;
  std::int64_t successes = 0;
  std::int64_t failures = 0;
  std::int64_t retries_attempted = 0;
  std::int64_t retries_denied_budget = 0;
  std::int64_t retries_exhausted = 0;
  double total_backoff_ms = 0.0;
  double success_rate = 0.0;
  double success_rate_without_retry = 0.0;  // fraction that succeed on attempt 1
};

// Exponential backoff for a given attempt (0-indexed retry number) with jitter.
double backoff_for(const RetryConfig& cfg, int retry_index, Xorshift64& rng);

RetryReport run_retry(const std::vector<RetryRequest>& requests, const RetryConfig& cfg);

RetryReport run_retry_wire(const std::string& text);

}  // namespace tryops

#endif  // TRYOPS_RETRY_HPP
