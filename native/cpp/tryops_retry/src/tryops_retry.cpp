#include "tryops_retry.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <sstream>

namespace tryops {

double backoff_for(const RetryConfig& cfg, int retry_index, Xorshift64& rng) {
  // exponential: base * 2^retry_index, capped at max
  double exp = cfg.base_backoff_ms * std::pow(2.0, static_cast<double>(retry_index));
  exp = std::min(exp, cfg.max_backoff_ms);
  switch (cfg.jitter) {
    case Jitter::kNone:
      return exp;
    case Jitter::kFull:
      return rng.unit() * exp;  // [0, exp)
    case Jitter::kEqual:
      return exp / 2.0 + rng.unit() * (exp / 2.0);  // [exp/2, exp)
  }
  return exp;
}

RetryReport run_retry(const std::vector<RetryRequest>& requests, const RetryConfig& cfg) {
  RetryReport rep;
  Xorshift64 rng(cfg.seed);
  std::int64_t first_try_success = 0;

  for (const auto& req : requests) {
    rep.requests += 1;
    if (req.attempts_needed <= 1) {
      first_try_success += 1;
    }

    int attempt = 1;
    bool succeeded = false;
    while (true) {
      if (attempt >= req.attempts_needed) {
        succeeded = true;
        break;
      }
      // this attempt failed; decide whether to retry.
      if (attempt > cfg.max_retries) {
        rep.retries_exhausted += 1;
        break;
      }
      // retry budget: cumulative retries capped at ratio * requests-so-far.
      const double allowed =
          std::floor(static_cast<double>(rep.requests) * cfg.retry_budget_ratio);
      if (static_cast<double>(rep.retries_attempted) >= allowed) {
        rep.retries_denied_budget += 1;
        break;  // give up rather than amplify load
      }
      // perform the retry with backoff.
      rep.total_backoff_ms += backoff_for(cfg, attempt - 1, rng);
      rep.retries_attempted += 1;
      attempt += 1;
    }

    if (succeeded) {
      rep.successes += 1;
    } else {
      rep.failures += 1;
    }
  }

  rep.success_rate =
      rep.requests > 0 ? static_cast<double>(rep.successes) / rep.requests : 0.0;
  rep.success_rate_without_retry =
      rep.requests > 0 ? static_cast<double>(first_try_success) / rep.requests : 0.0;
  return rep;
}

namespace {

Jitter parse_jitter(const std::string& v) {
  if (v == "none") return Jitter::kNone;
  if (v == "equal") return Jitter::kEqual;
  return Jitter::kFull;
}

}  // namespace

RetryReport run_retry_wire(const std::string& text) {
  RetryConfig cfg;
  std::vector<RetryRequest> requests;

  std::istringstream stream(text);
  std::string line;
  while (std::getline(stream, line)) {
    if (line.empty()) continue;
    const auto sep = line.find('=');
    if (sep == std::string::npos) continue;
    const std::string key = line.substr(0, sep);
    const std::string value = line.substr(sep + 1);
    if (key == "max_retries") {
      cfg.max_retries = std::atoi(value.c_str());
    } else if (key == "base_backoff_ms") {
      cfg.base_backoff_ms = std::atof(value.c_str());
    } else if (key == "max_backoff_ms") {
      cfg.max_backoff_ms = std::atof(value.c_str());
    } else if (key == "jitter") {
      cfg.jitter = parse_jitter(value);
    } else if (key == "retry_budget_ratio") {
      cfg.retry_budget_ratio = std::atof(value.c_str());
    } else if (key == "seed") {
      cfg.seed = static_cast<std::uint64_t>(std::strtoull(value.c_str(), nullptr, 10));
    } else if (key == "request") {
      RetryRequest req;
      std::istringstream fields(value);
      std::string field;
      while (std::getline(fields, field, ';')) {
        const auto fsep = field.find('=');
        if (fsep == std::string::npos) continue;
        const std::string fk = field.substr(0, fsep);
        const std::string fv = field.substr(fsep + 1);
        if (fk == "attempts_needed") {
          req.attempts_needed = std::atoi(fv.c_str());
        }
      }
      requests.push_back(req);
    }
  }

  return run_retry(requests, cfg);
}

}  // namespace tryops
