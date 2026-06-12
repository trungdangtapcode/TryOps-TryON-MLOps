#include "tryops_admission.hpp"

#include <algorithm>
#include <cstdlib>
#include <sstream>

namespace tryops {
namespace {

double parse_double(const std::string& value, double fallback) {
  if (value.empty()) {
    return fallback;
  }
  return std::atof(value.c_str());
}

std::int64_t parse_i64(const std::string& value, std::int64_t fallback) {
  if (value.empty()) {
    return fallback;
  }
  return static_cast<std::int64_t>(std::atoll(value.c_str()));
}

int parse_int(const std::string& value, int fallback) {
  if (value.empty()) {
    return fallback;
  }
  return std::atoi(value.c_str());
}

}  // namespace

AdmissionController::AdmissionController(const AdmissionConfig& config)
    : config_(config), tokens_(config.bucket_capacity) {
  report_.min_tokens = config.bucket_capacity;
}

void AdmissionController::refill(std::int64_t now_ms) {
  if (!started_) {
    last_refill_ms_ = now_ms;
    started_ = true;
    return;
  }
  if (now_ms <= last_refill_ms_) {
    return;
  }
  const double elapsed_sec = static_cast<double>(now_ms - last_refill_ms_) / 1000.0;
  tokens_ = std::min(config_.bucket_capacity,
                     tokens_ + elapsed_sec * config_.refill_per_sec);
  last_refill_ms_ = now_ms;
}

void AdmissionController::release_finished(std::int64_t now_ms) {
  while (!inflight_finish_ms_.empty() && inflight_finish_ms_.front() <= now_ms) {
    inflight_finish_ms_.pop_front();
  }
}

double AdmissionController::window_error_rate() const {
  if (outcome_window_.empty()) {
    return 0.0;
  }
  return static_cast<double>(outcome_errors_) /
         static_cast<double>(outcome_window_.size());
}

void AdmissionController::record_outcome(const std::string& outcome) {
  const int is_error = (outcome == "error") ? 1 : 0;
  outcome_window_.push_back(is_error);
  outcome_errors_ += is_error;
  while (static_cast<int>(outcome_window_.size()) > config_.breaker_window) {
    outcome_errors_ -= outcome_window_.front();
    outcome_window_.pop_front();
  }
}

RejectReason AdmissionController::admit(const RequestEvent& event) {
  report_.total += 1;
  refill(event.ts_ms);
  release_finished(event.ts_ms);

  // 1. Circuit breaker gate (fail fast when downstream is unhealthy).
  if (breaker_state_ == BreakerState::kOpen) {
    if (event.ts_ms - breaker_opened_ms_ >= config_.breaker_cooldown_ms) {
      breaker_state_ = BreakerState::kHalfOpen;  // allow a single probe through
    } else {
      report_.rejected_breaker_open += 1;
      return RejectReason::kBreakerOpen;
    }
  }

  // 2. Concurrency bulkhead.
  if (static_cast<int>(inflight_finish_ms_.size()) >= config_.max_concurrency) {
    report_.rejected_concurrency_full += 1;
    return RejectReason::kConcurrencyFull;
  }

  // 3. Token bucket rate limit.
  if (tokens_ < event.cost) {
    report_.rejected_rate_limited += 1;
    report_.min_tokens = std::min(report_.min_tokens, tokens_);
    return RejectReason::kRateLimited;
  }

  // Admit: consume tokens, occupy a slot, account the outcome.
  tokens_ -= event.cost;
  report_.min_tokens = std::min(report_.min_tokens, tokens_);
  const std::int64_t finish = event.ts_ms + std::max(0, event.duration_ms);
  inflight_finish_ms_.push_back(finish);
  report_.peak_inflight =
      std::max(report_.peak_inflight, static_cast<int>(inflight_finish_ms_.size()));
  report_.admitted += 1;

  record_outcome(event.outcome);

  // Breaker state machine on observed outcome.
  const bool was_half_open = (breaker_state_ == BreakerState::kHalfOpen);
  if (was_half_open) {
    if (event.outcome == "error") {
      breaker_state_ = BreakerState::kOpen;  // probe failed, re-open
      breaker_opened_ms_ = event.ts_ms;
      report_.breaker_trips += 1;
    } else {
      breaker_state_ = BreakerState::kClosed;  // probe succeeded, recover
      report_.breaker_recoveries += 1;
      outcome_window_.clear();
      outcome_errors_ = 0;
    }
  } else if (breaker_state_ == BreakerState::kClosed) {
    const int samples = static_cast<int>(outcome_window_.size());
    if (samples >= config_.breaker_min_samples &&
        window_error_rate() >= config_.breaker_error_threshold) {
      breaker_state_ = BreakerState::kOpen;
      breaker_opened_ms_ = event.ts_ms;
      report_.breaker_trips += 1;
    }
  }

  return RejectReason::kNone;
}

AdmissionReport AdmissionController::report() const {
  AdmissionReport out = report_;
  out.final_state = breaker_state_;
  out.admit_rate =
      out.total > 0 ? static_cast<double>(out.admitted) / out.total : 0.0;
  out.shed_rate = 1.0 - out.admit_rate;
  // observed_error_rate is computed by the wire runner which tracks all admitted
  // outcomes; here we report the window-bounded view if used standalone.
  return out;
}

AdmissionReport run_admission_wire(const std::string& text) {
  AdmissionConfig config;
  std::vector<RequestEvent> events;
  std::int64_t admitted_errors = 0;

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

    if (key == "bucket_capacity") {
      config.bucket_capacity = parse_double(value, config.bucket_capacity);
    } else if (key == "refill_per_sec") {
      config.refill_per_sec = parse_double(value, config.refill_per_sec);
    } else if (key == "max_concurrency") {
      config.max_concurrency = parse_int(value, config.max_concurrency);
    } else if (key == "breaker_window") {
      config.breaker_window = parse_int(value, config.breaker_window);
    } else if (key == "breaker_error_threshold") {
      config.breaker_error_threshold =
          parse_double(value, config.breaker_error_threshold);
    } else if (key == "breaker_cooldown_ms") {
      config.breaker_cooldown_ms = parse_i64(value, config.breaker_cooldown_ms);
    } else if (key == "breaker_min_samples") {
      config.breaker_min_samples = parse_int(value, config.breaker_min_samples);
    } else if (key == "event") {
      // value form: ts_ms=<n>;cost=<f>;duration_ms=<n>;outcome=<s>
      RequestEvent ev;
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
          ev.ts_ms = parse_i64(fv, ev.ts_ms);
        } else if (fk == "cost") {
          ev.cost = parse_double(fv, ev.cost);
        } else if (fk == "duration_ms") {
          ev.duration_ms = parse_int(fv, ev.duration_ms);
        } else if (fk == "outcome") {
          ev.outcome = fv;
        }
      }
      events.push_back(ev);
    }
  }

  AdmissionController controller(config);
  for (const auto& ev : events) {
    const RejectReason reason = controller.admit(ev);
    if (reason == RejectReason::kNone && ev.outcome == "error") {
      admitted_errors += 1;
    }
  }

  AdmissionReport report = controller.report();
  report.observed_error_rate =
      report.admitted > 0
          ? static_cast<double>(admitted_errors) / report.admitted
          : 0.0;
  return report;
}

const char* breaker_state_name(BreakerState state) {
  switch (state) {
    case BreakerState::kClosed:
      return "closed";
    case BreakerState::kOpen:
      return "open";
    case BreakerState::kHalfOpen:
      return "half_open";
  }
  return "closed";
}

const char* reject_reason_name(RejectReason reason) {
  switch (reason) {
    case RejectReason::kNone:
      return "admitted";
    case RejectReason::kRateLimited:
      return "rate_limited";
    case RejectReason::kBreakerOpen:
      return "breaker_open";
    case RejectReason::kConcurrencyFull:
      return "concurrency_full";
  }
  return "admitted";
}

}  // namespace tryops
