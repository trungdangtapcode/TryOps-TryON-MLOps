#pragma once

#include <map>
#include <string>
#include <vector>

namespace tryops {

constexpr const char* kNativeTraceLogEnvelopeSchema =
    "tryops.native_trace_log_envelope.v1";

struct NativeTraceLogEnvelope {
  std::string schema_version = kNativeTraceLogEnvelopeSchema;
  std::string timestamp;
  std::string observed_timestamp;
  std::string language = "cpp";
  std::string runtime = "native-cpp17";
  std::string component = "native-validator";
  std::string event_name = "tryops.cpp.trace_envelope.validation";
  std::string severity_text = "INFO";
  int severity_number = 9;
  std::string trace_id;
  std::string span_id;
  std::string trace_flags = "01";
  std::string traceparent;
  std::string request_id;
  std::string workload = "platform";
  std::map<std::string, std::string> resource;
  std::map<std::string, std::string> attributes;
};

struct TraceEnvelopeValidation {
  bool passed = false;
  std::vector<std::string> errors;
};

NativeTraceLogEnvelope default_trace_envelope();
NativeTraceLogEnvelope parse_trace_envelope_lines(
    const std::vector<std::string>& lines);
TraceEnvelopeValidation validate_trace_envelope(
    const NativeTraceLogEnvelope& envelope);
std::string trace_envelope_to_json(const NativeTraceLogEnvelope& envelope);
std::string validation_report_to_json(
    const NativeTraceLogEnvelope& envelope,
    const TraceEnvelopeValidation& validation);

}  // namespace tryops
