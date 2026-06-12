// tryops_batch_scheduler: native continuous-batching scheduler benchmark.
//
// This CLI keeps the LLM serving scheduling hot path in compiled C++ and uses
// Python only for artifact marshaling. It compares request-level static batching
// against iteration-level continuous batching for the same request stream.
//
// Protocol: read key=value lines from stdin and emit one JSON object on stdout.
// Required input keys:
//   request.arrival_ms=0,0,2,2
//   request.prefill_tokens=64,256,64,1024
//   request.decode_tokens=8,57,16,32
// Optional config keys:
//   config.max_num_seqs=4
//   config.prefill_token_ms=0.01
//   config.decode_step_ms=0.18
//   config.batch_growth_factor=0.08
//   config.static_batch_wait_ms=0

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

struct Request {
  std::size_t index = 0;
  double arrival_ms = 0.0;
  double prefill_tokens = 0.0;
  int decode_tokens = 0;
};

struct Completion {
  std::size_t index = 0;
  double arrival_ms = 0.0;
  double start_ms = 0.0;
  double finish_ms = 0.0;
  int decode_tokens = 0;
};

struct RunStats {
  double wall_ms = 0.0;
  double latency_avg_ms = 0.0;
  double latency_p50_ms = 0.0;
  double latency_p95_ms = 0.0;
  double wait_avg_ms = 0.0;
  double tokens_per_second = 0.0;
  double useful_decode_tokens = 0.0;
  double scheduled_decode_slots = 0.0;
  double decode_slot_utilization = 0.0;
  std::size_t completed_requests = 0;
  std::vector<Completion> completions;
};

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    if (ch == '\\' || ch == '"') {
      out << '\\' << ch;
    } else if (ch == '\n') {
      out << "\\n";
    } else {
      out << ch;
    }
  }
  return out.str();
}

std::unordered_map<std::string, std::string> read_payload() {
  std::unordered_map<std::string, std::string> payload;
  std::string line;
  while (std::getline(std::cin, line)) {
    const auto separator = line.find('=');
    if (separator == std::string::npos) {
      continue;
    }
    payload[line.substr(0, separator)] = line.substr(separator + 1);
  }
  return payload;
}

std::vector<double> parse_doubles(const std::string& csv) {
  std::vector<double> values;
  std::stringstream stream(csv);
  std::string token;
  while (std::getline(stream, token, ',')) {
    const auto begin = token.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
      continue;
    }
    const auto end = token.find_last_not_of(" \t\r\n");
    values.push_back(std::stod(token.substr(begin, end - begin + 1)));
  }
  return values;
}

std::vector<int> parse_ints(const std::string& csv) {
  std::vector<int> values;
  std::stringstream stream(csv);
  std::string token;
  while (std::getline(stream, token, ',')) {
    const auto begin = token.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
      continue;
    }
    const auto end = token.find_last_not_of(" \t\r\n");
    values.push_back(std::stoi(token.substr(begin, end - begin + 1)));
  }
  return values;
}

double get_double(
    const std::unordered_map<std::string, std::string>& payload,
    const std::string& key,
    double default_value) {
  const auto it = payload.find(key);
  return it == payload.end() ? default_value : std::stod(it->second);
}

int get_int(
    const std::unordered_map<std::string, std::string>& payload,
    const std::string& key,
    int default_value) {
  const auto it = payload.find(key);
  return it == payload.end() ? default_value : std::stoi(it->second);
}

double batch_factor(std::size_t batch_size, double growth_factor) {
  if (batch_size <= 1) {
    return 1.0;
  }
  return 1.0 + growth_factor * static_cast<double>(batch_size - 1);
}

double percentile(std::vector<double> values, double quantile) {
  if (values.empty()) {
    return 0.0;
  }
  std::sort(values.begin(), values.end());
  long index = std::lround((static_cast<double>(values.size()) - 1.0) * quantile);
  index = std::max<long>(0, std::min<long>(index, static_cast<long>(values.size()) - 1));
  return values[static_cast<std::size_t>(index)];
}

double mean(const std::vector<double>& values) {
  if (values.empty()) {
    return 0.0;
  }
  return std::accumulate(values.begin(), values.end(), 0.0) / static_cast<double>(values.size());
}

RunStats summarize(
    const std::vector<Request>& requests,
    std::vector<Completion> completions,
    double scheduled_decode_slots) {
  RunStats stats;
  stats.completed_requests = completions.size();
  stats.completions = completions;
  if (completions.empty()) {
    return stats;
  }
  std::sort(stats.completions.begin(), stats.completions.end(), [](const Completion& left, const Completion& right) {
    return left.index < right.index;
  });

  std::vector<double> latencies;
  std::vector<double> waits;
  double first_arrival = std::numeric_limits<double>::infinity();
  double last_finish = 0.0;
  double useful_decode_tokens = 0.0;
  for (const Completion& completion : stats.completions) {
    first_arrival = std::min(first_arrival, completion.arrival_ms);
    last_finish = std::max(last_finish, completion.finish_ms);
    latencies.push_back(completion.finish_ms - completion.arrival_ms);
    waits.push_back(completion.start_ms - completion.arrival_ms);
    useful_decode_tokens += static_cast<double>(completion.decode_tokens);
  }
  if (requests.empty()) {
    first_arrival = 0.0;
  }
  stats.wall_ms = std::max(0.0, last_finish - first_arrival);
  stats.latency_avg_ms = mean(latencies);
  stats.latency_p50_ms = percentile(latencies, 0.50);
  stats.latency_p95_ms = percentile(latencies, 0.95);
  stats.wait_avg_ms = mean(waits);
  stats.useful_decode_tokens = useful_decode_tokens;
  stats.scheduled_decode_slots = scheduled_decode_slots;
  stats.decode_slot_utilization = scheduled_decode_slots <= 0.0 ? 0.0 : useful_decode_tokens / scheduled_decode_slots;
  stats.tokens_per_second = stats.wall_ms <= 0.0 ? 0.0 : useful_decode_tokens / (stats.wall_ms / 1000.0);
  return stats;
}

RunStats simulate_static(
    const std::vector<Request>& requests,
    int max_num_seqs,
    double prefill_token_ms,
    double decode_step_ms,
    double batch_growth_factor,
    double static_batch_wait_ms) {
  std::vector<Request> ordered = requests;
  std::sort(ordered.begin(), ordered.end(), [](const Request& left, const Request& right) {
    if (left.arrival_ms == right.arrival_ms) {
      return left.index < right.index;
    }
    return left.arrival_ms < right.arrival_ms;
  });

  std::vector<Completion> completions;
  double scheduled_decode_slots = 0.0;
  double now = ordered.empty() ? 0.0 : ordered.front().arrival_ms;
  std::size_t cursor = 0;
  while (cursor < ordered.size()) {
    now = std::max(now, ordered[cursor].arrival_ms);
    const double admit_until = now + static_batch_wait_ms;
    std::vector<Request> batch;
    while (cursor < ordered.size() && ordered[cursor].arrival_ms <= admit_until &&
           batch.size() < static_cast<std::size_t>(max_num_seqs)) {
      batch.push_back(ordered[cursor]);
      ++cursor;
    }
    if (batch.empty()) {
      continue;
    }

    double max_prefill = 0.0;
    int max_decode = 0;
    for (const Request& request : batch) {
      max_prefill = std::max(max_prefill, request.prefill_tokens);
      max_decode = std::max(max_decode, request.decode_tokens);
    }

    const double factor = batch_factor(batch.size(), batch_growth_factor);
    const double start = now;
    const double duration =
        (max_prefill * prefill_token_ms + static_cast<double>(max_decode) * decode_step_ms) * factor;
    const double finish = start + duration;
    scheduled_decode_slots += static_cast<double>(batch.size() * static_cast<std::size_t>(max_decode));
    for (const Request& request : batch) {
      completions.push_back({request.index, request.arrival_ms, start, finish, request.decode_tokens});
    }
    now = finish;
  }
  return summarize(requests, completions, scheduled_decode_slots);
}

RunStats simulate_continuous(
    const std::vector<Request>& requests,
    int max_num_seqs,
    double prefill_token_ms,
    double decode_step_ms,
    double batch_growth_factor) {
  struct ActiveRequest {
    Request request;
    int remaining_decode = 0;
    double start_ms = 0.0;
  };

  std::vector<Request> ordered = requests;
  std::sort(ordered.begin(), ordered.end(), [](const Request& left, const Request& right) {
    if (left.arrival_ms == right.arrival_ms) {
      return left.index < right.index;
    }
    return left.arrival_ms < right.arrival_ms;
  });

  std::vector<ActiveRequest> active;
  std::vector<Completion> completions;
  double scheduled_decode_slots = 0.0;
  double now = ordered.empty() ? 0.0 : ordered.front().arrival_ms;
  std::size_t cursor = 0;

  while (cursor < ordered.size() || !active.empty()) {
    if (active.empty() && cursor < ordered.size() && now < ordered[cursor].arrival_ms) {
      now = ordered[cursor].arrival_ms;
    }

    std::vector<Request> admitted;
    while (cursor < ordered.size() && ordered[cursor].arrival_ms <= now &&
           active.size() + admitted.size() < static_cast<std::size_t>(max_num_seqs)) {
      admitted.push_back(ordered[cursor]);
      ++cursor;
    }
    if (!admitted.empty()) {
      double max_prefill = 0.0;
      for (const Request& request : admitted) {
        max_prefill = std::max(max_prefill, request.prefill_tokens);
      }
      const double factor = batch_factor(admitted.size(), batch_growth_factor);
      now += max_prefill * prefill_token_ms * factor;
      for (const Request& request : admitted) {
        active.push_back({request, request.decode_tokens, now});
      }
    }

    if (active.empty()) {
      continue;
    }

    const double step_ms = decode_step_ms * batch_factor(active.size(), batch_growth_factor);
    now += step_ms;
    scheduled_decode_slots += static_cast<double>(active.size());

    std::vector<ActiveRequest> still_active;
    for (ActiveRequest& item : active) {
      item.remaining_decode -= 1;
      if (item.remaining_decode <= 0) {
        completions.push_back({
            item.request.index,
            item.request.arrival_ms,
            item.start_ms,
            now,
            item.request.decode_tokens,
        });
      } else {
        still_active.push_back(item);
      }
    }
    active.swap(still_active);
  }
  return summarize(requests, completions, scheduled_decode_slots);
}

void emit_run_stats(const RunStats& stats) {
  std::cout << "{";
  std::cout << "\"completed_requests\":" << stats.completed_requests << ",";
  std::cout << "\"wall_ms\":" << stats.wall_ms << ",";
  std::cout << "\"latency_avg_ms\":" << stats.latency_avg_ms << ",";
  std::cout << "\"latency_p50_ms\":" << stats.latency_p50_ms << ",";
  std::cout << "\"latency_p95_ms\":" << stats.latency_p95_ms << ",";
  std::cout << "\"wait_avg_ms\":" << stats.wait_avg_ms << ",";
  std::cout << "\"tokens_per_second\":" << stats.tokens_per_second << ",";
  std::cout << "\"useful_decode_tokens\":" << stats.useful_decode_tokens << ",";
  std::cout << "\"scheduled_decode_slots\":" << stats.scheduled_decode_slots << ",";
  std::cout << "\"decode_slot_utilization\":" << stats.decode_slot_utilization;
  std::cout << "}";
}

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    const auto arrival_it = payload.find("request.arrival_ms");
    const auto prefill_it = payload.find("request.prefill_tokens");
    const auto decode_it = payload.find("request.decode_tokens");
    if (arrival_it == payload.end() || prefill_it == payload.end() || decode_it == payload.end()) {
      throw std::runtime_error("missing required request.arrival_ms, request.prefill_tokens, or request.decode_tokens");
    }

    const std::vector<double> arrivals = parse_doubles(arrival_it->second);
    const std::vector<double> prefills = parse_doubles(prefill_it->second);
    const std::vector<int> decodes = parse_ints(decode_it->second);
    if (arrivals.empty()) {
      throw std::runtime_error("request stream is empty");
    }
    if (arrivals.size() != prefills.size() || arrivals.size() != decodes.size()) {
      throw std::runtime_error("request arrays must have equal length");
    }

    const int max_num_seqs = get_int(payload, "config.max_num_seqs", 4);
    const double prefill_token_ms = get_double(payload, "config.prefill_token_ms", 0.01);
    const double decode_step_ms = get_double(payload, "config.decode_step_ms", 0.18);
    const double batch_growth_factor = get_double(payload, "config.batch_growth_factor", 0.08);
    const double static_batch_wait_ms = get_double(payload, "config.static_batch_wait_ms", 0.0);
    if (max_num_seqs < 1) {
      throw std::runtime_error("config.max_num_seqs must be positive");
    }
    if (prefill_token_ms < 0.0 || decode_step_ms <= 0.0 || batch_growth_factor < 0.0 ||
        static_batch_wait_ms < 0.0) {
      throw std::runtime_error("scheduler timing config must be non-negative, and decode_step_ms must be positive");
    }

    std::vector<Request> requests;
    requests.reserve(arrivals.size());
    for (std::size_t index = 0; index < arrivals.size(); ++index) {
      if (prefills[index] < 0.0 || decodes[index] < 1) {
        throw std::runtime_error("request tokens must be non-negative prefill and positive decode");
      }
      requests.push_back({index, arrivals[index], prefills[index], decodes[index]});
    }

    const RunStats static_stats = simulate_static(
        requests,
        max_num_seqs,
        prefill_token_ms,
        decode_step_ms,
        batch_growth_factor,
        static_batch_wait_ms);
    const RunStats continuous_stats = simulate_continuous(
        requests,
        max_num_seqs,
        prefill_token_ms,
        decode_step_ms,
        batch_growth_factor);

    const double throughput_gain =
        static_stats.tokens_per_second <= 0.0
            ? 0.0
            : continuous_stats.tokens_per_second / static_stats.tokens_per_second;
    const double latency_reduction =
        static_stats.latency_p95_ms <= 0.0
            ? 0.0
            : (static_stats.latency_p95_ms - continuous_stats.latency_p95_ms) /
                  static_stats.latency_p95_ms;
    const double utilization_gain =
        continuous_stats.decode_slot_utilization - static_stats.decode_slot_utilization;
    const bool passed =
        continuous_stats.completed_requests == requests.size() &&
        continuous_stats.tokens_per_second >= static_stats.tokens_per_second &&
        continuous_stats.latency_p95_ms <= static_stats.latency_p95_ms;

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "{";
    std::cout << "\"schema_version\":\"tryops.native_batch_scheduler.v1\",";
    std::cout << "\"engine\":\"native_cpp_iteration_scheduler\",";
    std::cout << "\"request_count\":" << requests.size() << ",";
    std::cout << "\"config\":{";
    std::cout << "\"max_num_seqs\":" << max_num_seqs << ",";
    std::cout << "\"prefill_token_ms\":" << prefill_token_ms << ",";
    std::cout << "\"decode_step_ms\":" << decode_step_ms << ",";
    std::cout << "\"batch_growth_factor\":" << batch_growth_factor << ",";
    std::cout << "\"static_batch_wait_ms\":" << static_batch_wait_ms;
    std::cout << "},";
    std::cout << "\"static_batching\":";
    emit_run_stats(static_stats);
    std::cout << ",\"continuous_batching\":";
    emit_run_stats(continuous_stats);
    std::cout << ",\"comparison\":{";
    std::cout << "\"throughput_gain\":" << throughput_gain << ",";
    std::cout << "\"p95_latency_reduction_fraction\":" << latency_reduction << ",";
    std::cout << "\"decode_slot_utilization_gain\":" << utilization_gain << ",";
    std::cout << "\"continuous_better_or_equal\":" << (passed ? "true" : "false");
    std::cout << "},";
    std::cout << "\"passed\":" << (passed ? "true" : "false");
    std::cout << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
