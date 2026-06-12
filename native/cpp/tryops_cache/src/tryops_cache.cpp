#include "tryops_cache.hpp"

#include <cstdlib>
#include <sstream>
#include <utility>
#include <vector>

namespace tryops {

LruTtlCache::LruTtlCache(const CacheConfig& config) : config_(config) {
  if (config_.capacity == 0) {
    config_.capacity = 1;
  }
}

void LruTtlCache::touch(std::list<Node>::iterator it, std::int64_t now_ms) {
  it->expire_at = now_ms + config_.ttl_ms;  // sliding TTL on access
  lru_.splice(lru_.begin(), lru_, it);      // move to front (MRU)
}

void LruTtlCache::insert(const std::string& key, std::int64_t now_ms) {
  if (map_.size() >= config_.capacity) {
    // evict least-recently-used (tail)
    const Node& victim = lru_.back();
    map_.erase(victim.key);
    lru_.pop_back();
    report_.evictions += 1;
  }
  lru_.push_front(Node{key, now_ms + config_.ttl_ms});
  map_[key] = lru_.begin();
}

bool LruTtlCache::access(const std::string& key, std::int64_t now_ms) {
  report_.total += 1;
  auto found = map_.find(key);
  if (found != map_.end()) {
    auto it = found->second;
    if (it->expire_at > now_ms) {
      report_.hits += 1;
      touch(it, now_ms);
      report_.final_size = map_.size();
      report_.hit_rate =
          static_cast<double>(report_.hits) / report_.total;
      return true;
    }
    // expired: remove and fall through to miss/insert
    report_.expirations += 1;
    lru_.erase(it);
    map_.erase(found);
  }
  report_.misses += 1;
  insert(key, now_ms);
  report_.final_size = map_.size();
  report_.hit_rate = static_cast<double>(report_.hits) / report_.total;
  return false;
}

CacheReport run_cache_wire(const std::string& text) {
  CacheConfig config;
  LruTtlCache* cache = nullptr;
  CacheReport last{};

  std::istringstream stream(text);
  std::string line;
  // first pass: read config lines until the first event, then construct.
  std::vector<std::pair<std::int64_t, std::string>> events;
  while (std::getline(stream, line)) {
    if (line.empty()) {
      continue;
    }
    const auto sep = line.find('=');
    if (sep == std::string::npos) {
      continue;
    }
    const std::string key = line.substr(0, sep);
    const std::string value = line.substr(sep + 1);
    if (key == "capacity") {
      config.capacity = static_cast<std::size_t>(std::atoll(value.c_str()));
    } else if (key == "ttl_ms") {
      config.ttl_ms = static_cast<std::int64_t>(std::atoll(value.c_str()));
    } else if (key == "event") {
      std::int64_t ts = 0;
      std::string ekey;
      std::istringstream fields(value);
      std::string field;
      while (std::getline(fields, field, ';')) {
        const auto fsep = field.find('=');
        if (fsep == std::string::npos) {
          continue;
        }
        const std::string fk = field.substr(0, fsep);
        const std::string fv = field.substr(fsep + 1);
        if (fk == "ts_ms") {
          ts = static_cast<std::int64_t>(std::atoll(fv.c_str()));
        } else if (fk == "key") {
          ekey = fv;
        }
      }
      events.emplace_back(ts, ekey);
    }
  }

  cache = new LruTtlCache(config);
  for (const auto& ev : events) {
    cache->access(ev.second, ev.first);
  }
  last = cache->report();
  last.final_size = cache->size();
  delete cache;
  return last;
}

}  // namespace tryops
