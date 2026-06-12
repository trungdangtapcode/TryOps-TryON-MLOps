// Minimal assertion-based tests for the admission controller. Built and run by
// `make native-admission-test`.
#include "tryops_admission.hpp"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>

namespace {

int failures = 0;

void check(bool cond, const char* what) {
  if (!cond) {
    std::printf("FAIL: %s\n", what);
    failures += 1;
  }
}

bool approx(double a, double b) { return std::fabs(a - b) < 1e-6; }

// Rate limiting: a tight bucket with no refill admits exactly capacity/cost
// requests issued at the same instant, sheds the rest.
void test_rate_limit() {
  std::string wire =
      "bucket_capacity=3\nrefill_per_sec=0\nmax_concurrency=100\n";
  for (int i = 0; i < 10; ++i) {
    wire += "event=ts_ms=0;cost=1;duration_ms=0;outcome=ok\n";
  }
  const auto r = tryops::run_admission_wire(wire);
  check(r.total == 10, "rate_limit total");
  check(r.admitted == 3, "rate_limit admitted == capacity");
  check(r.rejected_rate_limited == 7, "rate_limit rejected");
  check(approx(r.admit_rate, 0.3), "rate_limit admit_rate");
}

// Refill restores burst capacity over time.
void test_refill() {
  // capacity 1, refill 1000/sec => 1 token per ms. Two events 1ms apart both
  // admit because the second ms refills the spent token.
  std::string wire =
      "bucket_capacity=1\nrefill_per_sec=1000\nmax_concurrency=100\n"
      "event=ts_ms=0;cost=1;duration_ms=0;outcome=ok\n"
      "event=ts_ms=1;cost=1;duration_ms=0;outcome=ok\n";
  const auto r = tryops::run_admission_wire(wire);
  check(r.admitted == 2, "refill admits after replenish");
}

// Concurrency bulkhead: long-running requests occupy slots and block new ones
// until they finish.
void test_concurrency() {
  std::string wire =
      "bucket_capacity=1000\nrefill_per_sec=1000\nmax_concurrency=2\n";
  // three simultaneous 100ms requests -> only 2 slots, third is shed
  wire += "event=ts_ms=0;cost=1;duration_ms=100;outcome=ok\n";
  wire += "event=ts_ms=0;cost=1;duration_ms=100;outcome=ok\n";
  wire += "event=ts_ms=0;cost=1;duration_ms=100;outcome=ok\n";
  // one after they finish -> admitted
  wire += "event=ts_ms=200;cost=1;duration_ms=10;outcome=ok\n";
  const auto r = tryops::run_admission_wire(wire);
  check(r.rejected_concurrency_full == 1, "concurrency shed one");
  check(r.peak_inflight == 2, "concurrency peak == limit");
  check(r.admitted == 3, "concurrency admits after release");
}

// Circuit breaker: a burst of errors trips it open; later requests are shed
// until the cooldown elapses, then a healthy probe closes it.
void test_breaker() {
  std::string wire =
      "bucket_capacity=1000\nrefill_per_sec=1000\nmax_concurrency=1000\n"
      "breaker_window=10\nbreaker_error_threshold=0.5\n"
      "breaker_cooldown_ms=1000\nbreaker_min_samples=5\n";
  // 6 errors in a row -> error rate 1.0 >= 0.5 with >=5 samples -> trips
  for (int i = 0; i < 6; ++i) {
    wire += "event=ts_ms=" + std::to_string(i) +
            ";cost=1;duration_ms=0;outcome=error\n";
  }
  // immediately after, still within cooldown -> breaker_open rejects
  wire += "event=ts_ms=10;cost=1;duration_ms=0;outcome=ok\n";
  // after cooldown -> half-open probe, ok -> recover/close
  wire += "event=ts_ms=2000;cost=1;duration_ms=0;outcome=ok\n";
  const auto r = tryops::run_admission_wire(wire);
  check(r.breaker_trips >= 1, "breaker tripped");
  check(r.rejected_breaker_open >= 1, "breaker shed while open");
  check(r.breaker_recoveries == 1, "breaker recovered");
  check(r.final_state == tryops::BreakerState::kClosed, "breaker closed at end");
}

// All-healthy traffic under ample capacity admits everything, breaker stays
// closed.
void test_happy_path() {
  std::string wire =
      "bucket_capacity=1000\nrefill_per_sec=1000\nmax_concurrency=1000\n";
  for (int i = 0; i < 50; ++i) {
    wire += "event=ts_ms=" + std::to_string(i * 10) +
            ";cost=1;duration_ms=1;outcome=ok\n";
  }
  const auto r = tryops::run_admission_wire(wire);
  check(r.admitted == 50, "happy admits all");
  check(approx(r.shed_rate, 0.0), "happy shed_rate zero");
  check(r.final_state == tryops::BreakerState::kClosed, "happy stays closed");
}

}  // namespace

int main() {
  test_rate_limit();
  test_refill();
  test_concurrency();
  test_breaker();
  test_happy_path();
  if (failures == 0) {
    std::printf("ok: all admission tests passed\n");
    return 0;
  }
  std::printf("FAILED: %d admission checks\n", failures);
  return 1;
}
