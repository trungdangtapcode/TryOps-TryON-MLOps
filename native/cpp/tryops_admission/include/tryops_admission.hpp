// TryOps native admission controller.
//
// Pushes the request-admission hot path down to a low-level engine: a token
// bucket (rate limiting), a circuit breaker (fault isolation with half-open
// probing), and concurrency-based load shedding (bulkhead). Python orchestrates;
// this code decides admit/reject per request on the production boundary.
//
// The controller is deterministic given an ordered event stream, which makes it
// replayable and unit-testable offline.
#ifndef TRYOPS_ADMISSION_HPP
#define TRYOPS_ADMISSION_HPP

#include <cstdint>
#include <deque>
#include <string>
#include <vector>

namespace tryops {

// One request arriving at the boundary.
struct RequestEvent {
  std::int64_t ts_ms = 0;   // monotonic arrival time in milliseconds
  double cost = 1.0;        // tokens consumed if admitted (e.g. estimated tokens)
  int duration_ms = 0;      // how long the work occupies a concurrency slot
  std::string outcome = "ok";  // "ok" or "error" — feeds the circuit breaker
};

struct AdmissionConfig {
  double bucket_capacity = 100.0;    // max burst (tokens)
  double refill_per_sec = 50.0;      // sustained admit rate (tokens/sec)
  int max_concurrency = 32;          // bulkhead limit (in-flight slots)
  int breaker_window = 20;           // sliding window of recent admitted outcomes
  double breaker_error_threshold = 0.5;  // open when error-rate >= this
  std::int64_t breaker_cooldown_ms = 1000;  // open -> half-open delay
  int breaker_min_samples = 5;       // don't trip before this many samples
};

enum class RejectReason {
  kNone,
  kRateLimited,
  kBreakerOpen,
  kConcurrencyFull,
};

enum class BreakerState {
  kClosed,
  kOpen,
  kHalfOpen,
};

struct AdmissionReport {
  std::int64_t total = 0;
  std::int64_t admitted = 0;
  std::int64_t rejected_rate_limited = 0;
  std::int64_t rejected_breaker_open = 0;
  std::int64_t rejected_concurrency_full = 0;
  std::int64_t breaker_trips = 0;        // closed/half-open -> open transitions
  std::int64_t breaker_recoveries = 0;   // half-open -> closed transitions
  int peak_inflight = 0;
  double min_tokens = 0.0;
  double admit_rate = 0.0;               // admitted / total
  double shed_rate = 0.0;                // 1 - admit_rate
  double observed_error_rate = 0.0;      // errors / admitted
  BreakerState final_state = BreakerState::kClosed;
};

// Stateful controller. Feed events in non-decreasing ts_ms order.
class AdmissionController {
 public:
  explicit AdmissionController(const AdmissionConfig& config);

  // Returns the reason a request was rejected, or kNone if admitted.
  RejectReason admit(const RequestEvent& event);

  // Snapshot of accumulated decisions.
  AdmissionReport report() const;

  BreakerState breaker_state() const { return breaker_state_; }
  double tokens() const { return tokens_; }

 private:
  void refill(std::int64_t now_ms);
  void release_finished(std::int64_t now_ms);
  void record_outcome(const std::string& outcome);
  double window_error_rate() const;

  AdmissionConfig config_;
  double tokens_;
  std::int64_t last_refill_ms_ = 0;
  bool started_ = false;

  // Concurrency bulkhead: heap of finish times for in-flight requests.
  std::deque<std::int64_t> inflight_finish_ms_;

  // Circuit breaker state.
  BreakerState breaker_state_ = BreakerState::kClosed;
  std::int64_t breaker_opened_ms_ = 0;
  std::deque<int> outcome_window_;  // 1 = error, 0 = ok
  int outcome_errors_ = 0;

  AdmissionReport report_;
};

// Parse a `key=value` config/event wire stream from `text` and run the
// controller over it. Lines:
//   bucket_capacity=...  refill_per_sec=...  max_concurrency=... etc.
//   event=ts_ms=<n>;cost=<f>;duration_ms=<n>;outcome=<ok|error>
AdmissionReport run_admission_wire(const std::string& text);

const char* breaker_state_name(BreakerState state);
const char* reject_reason_name(RejectReason reason);

}  // namespace tryops

#endif  // TRYOPS_ADMISSION_HPP
