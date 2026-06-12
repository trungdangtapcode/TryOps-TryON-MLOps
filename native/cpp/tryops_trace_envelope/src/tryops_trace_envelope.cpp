#include "tryops_trace_envelope.hpp"

#include <chrono>
#include <cctype>
#include <sstream>

namespace tryops {
namespace {

bool starts_with(const std::string& value, const std::string& prefix) {
  return value.rfind(prefix, 0) == 0;
}

std::string strip_prefix(const std::string& value, const std::string& prefix) {
  return value.substr(prefix.size());
}

std::string now_millis() {
  const auto now = std::chrono::system_clock::now().time_since_epoch();
  const auto millis =
      std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
  return std::to_string(millis);
}

bool is_lower_hex_len(const std::string& value, const std::size_t length) {
  if (value.size() != length) {
    return false;
  }
  for (const char ch : value) {
    const auto byte = static_cast<unsigned char>(ch);
    if (!std::isdigit(byte) && !(ch >= 'a' && ch <= 'f')) {
      return false;
    }
  }
  return true;
}

bool is_all_zero(const std::string& value) {
  for (const char ch : value) {
    if (ch != '0') {
      return false;
    }
  }
  return true;
}

std::string escape_json(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    switch (ch) {
      case '\\':
        out << "\\\\";
        break;
      case '"':
        out << "\\\"";
        break;
      case '\n':
        out << "\\n";
        break;
      case '\r':
        out << "\\r";
        break;
      case '\t':
        out << "\\t";
        break;
      default:
        out << ch;
        break;
    }
  }
  return out.str();
}

std::string map_to_json(const std::map<std::string, std::string>& values) {
  std::ostringstream out;
  out << "{";
  bool first = true;
  for (const auto& item : values) {
    if (!first) {
      out << ",";
    }
    first = false;
    out << "\"" << escape_json(item.first) << "\":";
    out << "\"" << escape_json(item.second) << "\"";
  }
  out << "}";
  return out.str();
}

void apply_line(const std::string& line, NativeTraceLogEnvelope& envelope) {
  const auto separator = line.find('=');
  if (separator == std::string::npos) {
    return;
  }
  const std::string key = line.substr(0, separator);
  const std::string value = line.substr(separator + 1);
  if (key == "schema_version") {
    envelope.schema_version = value;
  } else if (key == "timestamp") {
    envelope.timestamp = value;
  } else if (key == "observed_timestamp") {
    envelope.observed_timestamp = value;
  } else if (key == "language") {
    envelope.language = value;
  } else if (key == "runtime") {
    envelope.runtime = value;
  } else if (key == "component") {
    envelope.component = value;
  } else if (key == "event_name") {
    envelope.event_name = value;
  } else if (key == "severity_text") {
    envelope.severity_text = value;
  } else if (key == "severity_number") {
    envelope.severity_number = std::stoi(value);
  } else if (key == "trace_id") {
    envelope.trace_id = value;
  } else if (key == "span_id") {
    envelope.span_id = value;
  } else if (key == "trace_flags") {
    envelope.trace_flags = value;
  } else if (key == "traceparent") {
    envelope.traceparent = value;
  } else if (key == "request_id") {
    envelope.request_id = value;
  } else if (key == "workload") {
    envelope.workload = value;
  } else if (starts_with(key, "resource.")) {
    envelope.resource[strip_prefix(key, "resource.")] = value;
  } else if (starts_with(key, "attribute.")) {
    envelope.attributes[strip_prefix(key, "attribute.")] = value;
  }
}

}  // namespace

NativeTraceLogEnvelope default_trace_envelope() {
  NativeTraceLogEnvelope envelope;
  envelope.timestamp = now_millis();
  envelope.observed_timestamp = envelope.timestamp;
  envelope.trace_id = "11111111111111111111111111111111";
  envelope.span_id = "3333333333333333";
  envelope.traceparent =
      "00-" + envelope.trace_id + "-" + envelope.span_id + "-01";
  envelope.request_id = "req-cpp";
  envelope.workload = "platform";
  envelope.resource["service.name"] = "tryops-native-cpp";
  envelope.resource["service.version"] = "0.1.0";
  envelope.resource["telemetry.sdk.language"] = "cpp";
  envelope.attributes["status"] = "validated";
  envelope.attributes["endpoint"] = "native://trace-envelope";
  return envelope;
}

NativeTraceLogEnvelope parse_trace_envelope_lines(
    const std::vector<std::string>& lines) {
  NativeTraceLogEnvelope envelope = default_trace_envelope();
  for (const auto& line : lines) {
    apply_line(line, envelope);
  }
  if (envelope.traceparent.empty() && !envelope.trace_id.empty() &&
      !envelope.span_id.empty() && !envelope.trace_flags.empty()) {
    envelope.traceparent = "00-" + envelope.trace_id + "-" + envelope.span_id +
                           "-" + envelope.trace_flags;
  }
  return envelope;
}

TraceEnvelopeValidation validate_trace_envelope(
    const NativeTraceLogEnvelope& envelope) {
  TraceEnvelopeValidation validation;
  if (envelope.schema_version != kNativeTraceLogEnvelopeSchema) {
    validation.errors.push_back("schema_version mismatch");
  }
  if (!is_lower_hex_len(envelope.trace_id, 32) ||
      is_all_zero(envelope.trace_id)) {
    validation.errors.push_back("invalid trace_id");
  }
  if (!is_lower_hex_len(envelope.span_id, 16) ||
      is_all_zero(envelope.span_id)) {
    validation.errors.push_back("invalid span_id");
  }
  if (!is_lower_hex_len(envelope.trace_flags, 2)) {
    validation.errors.push_back("invalid trace_flags");
  }
  if (envelope.traceparent != "00-" + envelope.trace_id + "-" +
                                  envelope.span_id + "-" +
                                  envelope.trace_flags) {
    validation.errors.push_back("traceparent does not match trace fields");
  }
  const auto service_name = envelope.resource.find("service.name");
  if (service_name == envelope.resource.end() || service_name->second.empty()) {
    validation.errors.push_back("resource.service.name is required");
  }
  const auto service_version = envelope.resource.find("service.version");
  if (service_version == envelope.resource.end() ||
      service_version->second.empty()) {
    validation.errors.push_back("resource.service.version is required");
  }
  if (envelope.event_name.empty()) {
    validation.errors.push_back("event_name is required");
  }
  if (envelope.severity_number <= 0) {
    validation.errors.push_back("severity_number must be positive");
  }
  validation.passed = validation.errors.empty();
  return validation;
}

std::string trace_envelope_to_json(const NativeTraceLogEnvelope& envelope) {
  std::ostringstream out;
  out << "{";
  out << "\"schema_version\":\"" << escape_json(envelope.schema_version)
      << "\",";
  out << "\"timestamp\":\"" << escape_json(envelope.timestamp) << "\",";
  out << "\"observed_timestamp\":\""
      << escape_json(envelope.observed_timestamp) << "\",";
  out << "\"language\":\"" << escape_json(envelope.language) << "\",";
  out << "\"runtime\":\"" << escape_json(envelope.runtime) << "\",";
  out << "\"component\":\"" << escape_json(envelope.component) << "\",";
  out << "\"event_name\":\"" << escape_json(envelope.event_name) << "\",";
  out << "\"severity_text\":\"" << escape_json(envelope.severity_text)
      << "\",";
  out << "\"severity_number\":" << envelope.severity_number << ",";
  out << "\"trace_id\":\"" << escape_json(envelope.trace_id) << "\",";
  out << "\"span_id\":\"" << escape_json(envelope.span_id) << "\",";
  out << "\"trace_flags\":\"" << escape_json(envelope.trace_flags) << "\",";
  out << "\"traceparent\":\"" << escape_json(envelope.traceparent) << "\",";
  out << "\"request_id\":\"" << escape_json(envelope.request_id) << "\",";
  out << "\"workload\":\"" << escape_json(envelope.workload) << "\",";
  out << "\"resource\":" << map_to_json(envelope.resource) << ",";
  out << "\"attributes\":" << map_to_json(envelope.attributes);
  out << "}";
  return out.str();
}

std::string validation_report_to_json(
    const NativeTraceLogEnvelope& envelope,
    const TraceEnvelopeValidation& validation) {
  std::ostringstream out;
  out << "{";
  out << "\"schema_version\":\"tryops.native_trace_envelope_validation.v1\",";
  out << "\"contract\":\"" << kNativeTraceLogEnvelopeSchema << "\",";
  out << "\"language\":\"cpp\",";
  out << "\"passed\":" << (validation.passed ? "true" : "false") << ",";
  out << "\"error_count\":" << validation.errors.size() << ",";
  out << "\"errors\":[";
  for (std::size_t index = 0; index < validation.errors.size(); ++index) {
    if (index != 0) {
      out << ",";
    }
    out << "\"" << escape_json(validation.errors[index]) << "\"";
  }
  out << "],";
  out << "\"envelope\":" << trace_envelope_to_json(envelope);
  out << "}";
  return out.str();
}

}  // namespace tryops
