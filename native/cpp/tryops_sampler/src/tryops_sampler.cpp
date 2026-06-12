#include "tryops_sampler.hpp"

#include <cstdlib>
#include <sstream>

namespace tryops {

SamplerReport reservoir_sample(const std::vector<TraceItem>& items,
                               std::size_t capacity, std::uint64_t seed) {
  SamplerReport rep;
  rep.capacity = capacity;
  Xorshift64 rng(seed);
  rep.sample.reserve(capacity);
  for (std::size_t i = 0; i < items.size(); ++i) {
    rep.observed += 1;
    if (items[i].priority) {
      rep.priority_seen += 1;
    }
    if (rep.sample.size() < capacity) {
      rep.sample.push_back(items[i].id);
    } else {
      const std::uint64_t j = rng.below(i + 1);
      if (j < capacity) {
        rep.sample[static_cast<std::size_t>(j)] = items[i].id;
      }
    }
  }
  return rep;
}

SamplerReport priority_sample(const std::vector<TraceItem>& items,
                              std::size_t capacity, std::uint64_t seed) {
  SamplerReport rep;
  rep.capacity = capacity;
  Xorshift64 rng(seed);

  // First pass: collect priority items (force-keep up to capacity) and the rest.
  std::vector<std::string> kept;
  std::vector<TraceItem> rest;
  for (const auto& it : items) {
    rep.observed += 1;
    if (it.priority) {
      rep.priority_seen += 1;
      if (kept.size() < capacity) {
        kept.push_back(it.id);
        rep.priority_kept += 1;
      }
    } else {
      rest.push_back(it);
    }
  }

  // Fill remaining capacity by reservoir over the non-priority items.
  const std::size_t remaining = capacity - kept.size();
  std::vector<std::string> filler;
  filler.reserve(remaining);
  for (std::size_t i = 0; i < rest.size(); ++i) {
    if (filler.size() < remaining) {
      filler.push_back(rest[i].id);
    } else if (remaining > 0) {
      const std::uint64_t j = rng.below(i + 1);
      if (j < remaining) {
        filler[static_cast<std::size_t>(j)] = rest[i].id;
      }
    }
  }

  rep.sample = std::move(kept);
  for (auto& f : filler) {
    rep.sample.push_back(std::move(f));
  }
  return rep;
}

SamplerReport run_sampler_wire(const std::string& text) {
  std::size_t capacity = 100;
  std::uint64_t seed = 1;
  std::string mode = "reservoir";
  std::vector<TraceItem> items;

  std::istringstream stream(text);
  std::string line;
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
      capacity = static_cast<std::size_t>(std::atoll(value.c_str()));
    } else if (key == "seed") {
      seed = static_cast<std::uint64_t>(std::strtoull(value.c_str(), nullptr, 10));
    } else if (key == "mode") {
      mode = value;
    } else if (key == "item") {
      TraceItem it;
      std::istringstream fields(value);
      std::string field;
      while (std::getline(fields, field, ';')) {
        const auto fsep = field.find('=');
        if (fsep == std::string::npos) {
          continue;
        }
        const std::string fk = field.substr(0, fsep);
        const std::string fv = field.substr(fsep + 1);
        if (fk == "id") {
          it.id = fv;
        } else if (fk == "priority") {
          it.priority = (fv == "1" || fv == "true");
        }
      }
      items.push_back(it);
    }
  }

  return mode == "priority" ? priority_sample(items, capacity, seed)
                            : reservoir_sample(items, capacity, seed);
}

}  // namespace tryops
