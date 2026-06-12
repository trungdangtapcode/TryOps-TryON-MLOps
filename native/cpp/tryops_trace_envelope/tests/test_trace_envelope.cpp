#include "tryops_trace_envelope.hpp"

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace {

void require(bool condition, const std::string& message) {
  if (!condition) {
    std::cerr << message << "\n";
    std::exit(1);
  }
}

bool has_error(
    const tryops::TraceEnvelopeValidation& validation,
    const std::string& expected) {
  for (const auto& error : validation.errors) {
    if (error == expected) {
      return true;
    }
  }
  return false;
}

}  // namespace

int main() {
  const auto valid = tryops::default_trace_envelope();
  const auto valid_result = tryops::validate_trace_envelope(valid);
  require(valid_result.passed, "default C++ trace envelope should pass");
  require(
      tryops::trace_envelope_to_json(valid).find(
          "tryops.native_trace_log_envelope.v1") != std::string::npos,
      "JSON should include shared envelope schema");

  const auto parsed = tryops::parse_trace_envelope_lines({
      "request_id=req-custom",
      "trace_id=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "span_id=bbbbbbbbbbbbbbbb",
      "trace_flags=01",
      "traceparent=00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
      "resource.service.name=tryops-native-cpp",
      "resource.service.version=0.1.0",
      "attribute.endpoint=/v1/llm/generate",
  });
  const auto parsed_result = tryops::validate_trace_envelope(parsed);
  require(parsed_result.passed, "parsed envelope should pass validation");

  auto invalid = parsed;
  invalid.trace_id = "00000000000000000000000000000000";
  invalid.traceparent = "00-00000000000000000000000000000000-bbbbbbbbbbbbbbbb-01";
  const auto invalid_result = tryops::validate_trace_envelope(invalid);
  require(!invalid_result.passed, "zero trace ID should fail validation");
  require(
      has_error(invalid_result, "invalid trace_id"),
      "zero trace ID should report invalid trace_id");
  return 0;
}
