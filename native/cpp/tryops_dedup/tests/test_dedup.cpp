#include "tryops_dedup.hpp"

#include <cstdio>
#include <set>
#include <string>

namespace {

int failures = 0;
void check(bool cond, const char* what) {
  if (!cond) { std::printf("FAIL: %s\n", what); failures += 1; }
}

// No false negatives: every real duplicate is caught.
void test_no_false_negatives() {
  tryops::BloomFilter f(1000, 0.01);
  for (int i = 0; i < 500; ++i) {
    f.insert_if_absent("key-" + std::to_string(i));
  }
  for (int i = 0; i < 500; ++i) {
    check(f.maybe_contains("key-" + std::to_string(i)), "inserted key found");
  }
}

// Dedup accounting: a stream of N unique keys each repeated twice admits N,
// rejects N.
void test_dedup_counts() {
  std::string wire = "expected_items=2000\ntarget_fp_rate=0.01\n";
  for (int pass = 0; pass < 2; ++pass) {
    for (int i = 0; i < 300; ++i) {
      wire += "key=req-" + std::to_string(i) + "\n";
    }
  }
  auto r = tryops::run_dedup_wire(wire);
  check(r.total == 600, "total");
  // admitted must be >= unique count is impossible; with no false negatives,
  // every second occurrence is rejected, so admitted == 300 exactly unless a
  // false positive rejects a first-seen key (rare). Allow a tiny slack.
  check(r.admitted <= 300, "admitted never exceeds unique");
  check(r.admitted >= 297, "admitted close to unique (few false positives)");
  check(r.rejected_dupe == r.total - r.admitted, "rejects = total - admitted");
}

// Sizing math sanity: more items / lower p => more bits.
void test_sizing() {
  auto m1 = tryops::optimal_bits(1000, 0.01);
  auto m2 = tryops::optimal_bits(1000, 0.0001);
  auto m3 = tryops::optimal_bits(100000, 0.01);
  check(m2 > m1, "lower fp-rate needs more bits");
  check(m3 > m1, "more items needs more bits");
  check(tryops::optimal_hashes(m1, 1000) >= 1, "at least one hash");
}

// Empirical false-positive rate stays near the configured target.
void test_fp_rate_within_bound() {
  tryops::BloomFilter f(10000, 0.01);
  for (int i = 0; i < 10000; ++i) {
    f.insert_if_absent("present-" + std::to_string(i));
  }
  int false_positives = 0;
  const int probes = 20000;
  for (int i = 0; i < probes; ++i) {
    if (f.maybe_contains("absent-" + std::to_string(i))) {
      false_positives += 1;
    }
  }
  const double rate = static_cast<double>(false_positives) / probes;
  // target 1% at full load; allow generous headroom for hash variance.
  check(rate < 0.03, "empirical fp-rate within 3x target");
}

}  // namespace

int main() {
  test_no_false_negatives();
  test_dedup_counts();
  test_sizing();
  test_fp_rate_within_bound();
  if (failures == 0) {
    std::printf("ok: all dedup tests passed\n");
    return 0;
  }
  std::printf("FAILED: %d dedup checks\n", failures);
  return 1;
}
