#include "tryops_retry.hpp"

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int failures = 0;
void check(bool cond, const char* what) {
  if (!cond) { std::printf("FAIL: %s\n", what); failures += 1; }
}

tryops::RetryConfig base() {
  tryops::RetryConfig c;
  c.max_retries = 3;
  c.base_backoff_ms = 50;
  c.max_backoff_ms = 2000;
  c.jitter = tryops::Jitter::kNone;
  c.retry_budget_ratio = 100.0;  // effectively unlimited for these tests
  c.seed = 7;
  return c;
}

// Retries recover transient failures.
void test_recovery() {
  std::vector<tryops::RetryRequest> reqs(100);
  for (auto& r : reqs) r.attempts_needed = 2;  // succeed on 2nd try
  auto rep = tryops::run_retry(reqs, base());
  check(rep.successes == 100, "all recovered with one retry");
  check(rep.retries_attempted == 100, "one retry each");
  check(std::fabs(rep.success_rate_without_retry - 0.0) < 1e-9, "0% without retry");
  check(std::fabs(rep.success_rate - 1.0) < 1e-9, "100% with retry");
}

// Requests needing more than max_retries+1 attempts exhaust and fail.
void test_exhaustion() {
  std::vector<tryops::RetryRequest> reqs(10);
  for (auto& r : reqs) r.attempts_needed = 10;  // needs 10, max 4 attempts
  auto rep = tryops::run_retry(reqs, base());
  check(rep.failures == 10, "all fail when unrecoverable");
  check(rep.retries_exhausted == 10, "exhaustion counted");
  check(rep.retries_attempted == 30, "3 retries each (max_retries)");
}

// Retry budget caps retries and prevents a storm.
void test_budget_cap() {
  auto cfg = base();
  cfg.retry_budget_ratio = 0.1;  // only 10% of requests may retry
  std::vector<tryops::RetryRequest> reqs(100);
  for (auto& r : reqs) r.attempts_needed = 2;
  auto rep = tryops::run_retry(reqs, cfg);
  // cumulative retries capped near 10 -> most requests denied retry -> fail
  check(rep.retries_attempted <= 11, "retries capped by budget");
  check(rep.retries_denied_budget > 0, "some retries denied");
  check(rep.successes < 100, "budget cap costs some recoveries");
}

// Backoff grows exponentially without jitter.
void test_backoff_growth() {
  auto cfg = base();
  tryops::Xorshift64 rng(1);
  double b0 = tryops::backoff_for(cfg, 0, rng);
  double b1 = tryops::backoff_for(cfg, 1, rng);
  double b2 = tryops::backoff_for(cfg, 2, rng);
  check(std::fabs(b0 - 50) < 1e-9, "b0 = base");
  check(std::fabs(b1 - 100) < 1e-9, "b1 = 2x");
  check(std::fabs(b2 - 200) < 1e-9, "b2 = 4x");
}

// Full jitter stays within [0, exp); equal jitter within [exp/2, exp).
void test_jitter_bounds() {
  auto cfg = base();
  cfg.jitter = tryops::Jitter::kFull;
  tryops::Xorshift64 rng(123);
  for (int i = 0; i < 1000; ++i) {
    double b = tryops::backoff_for(cfg, 1, rng);  // exp=100
    check(b >= 0.0 && b < 100.0 + 1e-9, "full jitter in range");
  }
  cfg.jitter = tryops::Jitter::kEqual;
  for (int i = 0; i < 1000; ++i) {
    double b = tryops::backoff_for(cfg, 1, rng);
    check(b >= 50.0 - 1e-9 && b < 100.0 + 1e-9, "equal jitter in range");
  }
}

}  // namespace

int main() {
  test_recovery();
  test_exhaustion();
  test_budget_cap();
  test_backoff_growth();
  test_jitter_bounds();
  if (failures == 0) { std::printf("ok: all retry tests passed\n"); return 0; }
  std::printf("FAILED: %d retry checks\n", failures);
  return 1;
}
