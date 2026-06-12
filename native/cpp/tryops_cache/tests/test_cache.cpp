#include "tryops_cache.hpp"

#include <cstdio>
#include <string>

namespace {

int failures = 0;
void check(bool cond, const char* what) {
  if (!cond) { std::printf("FAIL: %s\n", what); failures += 1; }
}

// Repeated access to the same key hits after the first miss.
void test_basic_hits() {
  tryops::CacheConfig cfg; cfg.capacity = 10; cfg.ttl_ms = 1000;
  tryops::LruTtlCache c(cfg);
  check(!c.access("a", 0), "first access miss");
  check(c.access("a", 1), "second access hit");
  check(c.access("a", 2), "third access hit");
  const auto& r = c.report();
  check(r.hits == 2 && r.misses == 1, "hit/miss counts");
}

// LRU eviction: capacity 2, three distinct keys -> first is evicted.
void test_lru_eviction() {
  tryops::CacheConfig cfg; cfg.capacity = 2; cfg.ttl_ms = 100000;
  tryops::LruTtlCache c(cfg);
  c.access("a", 0);
  c.access("b", 1);
  c.access("c", 2);            // evicts "a" (LRU)
  check(!c.access("a", 3), "evicted key misses");  // miss -> reinsert, evicts "b"
  check(c.report().evictions >= 2, "evictions counted");
}

// TTL expiry: an entry past its TTL is a miss.
void test_ttl_expiry() {
  tryops::CacheConfig cfg; cfg.capacity = 10; cfg.ttl_ms = 100;
  tryops::LruTtlCache c(cfg);
  c.access("k", 0);
  check(c.access("k", 50), "within ttl hit");
  check(!c.access("k", 1000), "past ttl miss");  // sliding ttl from t=50 -> expires by 1000
  check(c.report().expirations >= 1, "expiration counted");
}

// Hot-key workload yields a high hit rate via the wire runner.
void test_hot_key_hit_rate() {
  std::string wire = "capacity=100\nttl_ms=1000000\n";
  // 1000 accesses, 90% to a small hot set of 5 keys
  for (int i = 0; i < 1000; ++i) {
    const int k = (i % 10 < 9) ? (i % 5) : (100 + i);
    wire += "event=ts_ms=" + std::to_string(i) + ";key=hk-" + std::to_string(k) + "\n";
  }
  auto r = tryops::run_cache_wire(wire);
  check(r.total == 1000, "total");
  check(r.hit_rate > 0.6, "hot-key hit rate high");
}

// LRU keeps recently-used keys: re-touching a key prevents its eviction.
void test_recency_protects() {
  tryops::CacheConfig cfg; cfg.capacity = 2; cfg.ttl_ms = 100000;
  tryops::LruTtlCache c(cfg);
  c.access("a", 0);
  c.access("b", 1);
  c.access("a", 2);   // a is now MRU
  c.access("c", 3);   // evicts b (LRU), not a
  check(c.access("a", 4), "recently-used key survived");
}

}  // namespace

int main() {
  test_basic_hits();
  test_lru_eviction();
  test_ttl_expiry();
  test_hot_key_hit_rate();
  test_recency_protects();
  if (failures == 0) { std::printf("ok: all cache tests passed\n"); return 0; }
  std::printf("FAILED: %d cache checks\n", failures);
  return 1;
}
