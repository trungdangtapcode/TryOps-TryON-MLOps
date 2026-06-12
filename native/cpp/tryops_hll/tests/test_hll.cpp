#include "tryops_hll.hpp"

#include <cmath>
#include <cstdio>
#include <set>
#include <string>

namespace {

int failures = 0;
void check(bool cond, const char* what) {
  if (!cond) { std::printf("FAIL: %s\n", what); failures += 1; }
}

// Estimate is within a few standard errors of truth across magnitudes.
void test_accuracy_across_scales() {
  for (int true_n : {100, 1000, 10000, 100000}) {
    tryops::HyperLogLog hll(14);  // m=16384, ~0.8% std error
    for (int i = 0; i < true_n; ++i) {
      hll.add("user-" + std::to_string(i));
    }
    const double est = hll.estimate();
    const double rel_err = std::fabs(est - true_n) / true_n;
    // allow 4x the theoretical std error as a safe bound
    check(rel_err < 4.0 * hll.standard_error() + 0.01,
          ("accuracy within bound for n=" + std::to_string(true_n)).c_str());
  }
}

// Duplicates do not inflate the estimate.
void test_duplicates_ignored() {
  tryops::HyperLogLog hll(12);
  for (int rep = 0; rep < 50; ++rep) {
    for (int i = 0; i < 200; ++i) {
      hll.add("k-" + std::to_string(i));
    }
  }
  const double est = hll.estimate();
  check(std::fabs(est - 200.0) / 200.0 < 0.10, "dupes ignored (~200 distinct)");
}

// Empty stream estimates ~0.
void test_empty() {
  tryops::HyperLogLog hll(10);
  check(hll.estimate() < 1.0, "empty estimate near zero");
}

// Determinism: same input => same estimate.
void test_determinism() {
  tryops::HyperLogLog a(12), b(12);
  for (int i = 0; i < 5000; ++i) {
    a.add("x" + std::to_string(i));
    b.add("x" + std::to_string(i));
  }
  check(a.estimate() == b.estimate(), "deterministic estimate");
}

}  // namespace

int main() {
  test_accuracy_across_scales();
  test_duplicates_ignored();
  test_empty();
  test_determinism();
  if (failures == 0) {
    std::printf("ok: all hll tests passed\n");
    return 0;
  }
  std::printf("FAILED: %d hll checks\n", failures);
  return 1;
}
