#include "tryops_sampler.hpp"

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

namespace {

int failures = 0;
void check(bool cond, const char* what) {
  if (!cond) { std::printf("FAIL: %s\n", what); failures += 1; }
}

std::vector<tryops::TraceItem> make_items(int n, int every_priority = 0) {
  std::vector<tryops::TraceItem> v;
  for (int i = 0; i < n; ++i) {
    tryops::TraceItem it;
    it.id = "t-" + std::to_string(i);
    it.priority = every_priority > 0 && (i % every_priority == 0);
    v.push_back(it);
  }
  return v;
}

// Sample never exceeds capacity and equals capacity when n >= capacity.
void test_size() {
  auto items = make_items(1000);
  auto r = tryops::reservoir_sample(items, 50, 42);
  check(r.sample.size() == 50, "reservoir fills capacity");
  auto few = tryops::reservoir_sample(make_items(10), 50, 42);
  check(few.sample.size() == 10, "small stream kept whole");
}

// Determinism: same seed => identical sample.
void test_determinism() {
  auto items = make_items(5000);
  auto a = tryops::reservoir_sample(items, 100, 12345);
  auto b = tryops::reservoir_sample(items, 100, 12345);
  check(a.sample == b.sample, "same seed identical sample");
  auto c = tryops::reservoir_sample(items, 100, 99999);
  check(a.sample != c.sample, "different seed differs");
}

// Uniformity: over many seeds, each item is selected ~k/n of the time.
void test_uniformity() {
  const int n = 200, k = 20, trials = 4000;
  auto items = make_items(n);
  std::vector<int> count(n, 0);
  for (int s = 1; s <= trials; ++s) {
    auto r = tryops::reservoir_sample(items, k, static_cast<std::uint64_t>(s) * 2654435761ULL);
    for (const auto& id : r.sample) {
      count[std::atoi(id.c_str() + 2)] += 1;  // parse index after "t-"
    }
  }
  const double expected = static_cast<double>(trials) * k / n;  // each item
  int off = 0;
  for (int c : count) {
    if (std::fabs(c - expected) > 0.25 * expected) off += 1;
  }
  // allow a few items outside the 25% band due to variance
  check(off <= n / 10, "selection roughly uniform across items");
}

// Priority mode force-keeps flagged spans.
void test_priority_kept() {
  auto items = make_items(1000, 100);  // ~10 priority items
  auto r = tryops::priority_sample(items, 50, 7);
  check(r.priority_seen >= 9, "priority items seen");
  check(r.priority_kept == r.priority_seen, "all priority kept (fits capacity)");
  check(r.sample.size() == 50, "priority sample fills capacity");
  // first priority_kept entries are the priority ids
  check(r.sample[0] == "t-0", "priority item first in sample");
}

}  // namespace

int main() {
  test_size();
  test_determinism();
  test_uniformity();
  test_priority_kept();
  if (failures == 0) { std::printf("ok: all sampler tests passed\n"); return 0; }
  std::printf("FAILED: %d sampler checks\n", failures);
  return 1;
}
