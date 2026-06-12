// TryOps native response cache: fixed-capacity LRU with per-entry TTL.
//
// Sits at the edge to short-circuit repeated identical requests (e.g. a
// normalized prompt or a rendered VTON key). LRU eviction bounds memory; TTL
// bounds staleness. Deterministic given an ordered event stream, so cache
// behaviour (hit rate, evictions, expirations) is replayable and testable.
#ifndef TRYOPS_CACHE_HPP
#define TRYOPS_CACHE_HPP

#include <cstdint>
#include <list>
#include <string>
#include <unordered_map>

namespace tryops {

struct CacheConfig {
  std::size_t capacity = 1024;
  std::int64_t ttl_ms = 60000;  // default entry lifetime
};

struct CacheReport {
  std::int64_t total = 0;
  std::int64_t hits = 0;
  std::int64_t misses = 0;
  std::int64_t evictions = 0;    // LRU evictions
  std::int64_t expirations = 0;  // TTL expirations observed on access
  std::size_t final_size = 0;
  double hit_rate = 0.0;
};

// LRU cache keyed by string. value payloads are irrelevant to the simulation, so
// only presence + expiry are tracked.
class LruTtlCache {
 public:
  explicit LruTtlCache(const CacheConfig& config);

  // Look up a key at time `now_ms`. Returns true on a fresh hit. On a miss (or
  // an expired entry) the key is inserted, possibly evicting the LRU entry.
  bool access(const std::string& key, std::int64_t now_ms);

  std::size_t size() const { return map_.size(); }
  const CacheReport& report() const { return report_; }

 private:
  struct Node {
    std::string key;
    std::int64_t expire_at;
  };

  void touch(std::list<Node>::iterator it, std::int64_t now_ms);
  void insert(const std::string& key, std::int64_t now_ms);

  CacheConfig config_;
  std::list<Node> lru_;  // front = most-recently-used
  std::unordered_map<std::string, std::list<Node>::iterator> map_;
  CacheReport report_;
};

// Parse and run a wire stream:
//   capacity=...  ttl_ms=...
//   event=ts_ms=<n>;key=<k>
CacheReport run_cache_wire(const std::string& text);

}  // namespace tryops

#endif  // TRYOPS_CACHE_HPP
