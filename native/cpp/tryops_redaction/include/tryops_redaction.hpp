// TryOps native PII / secret redaction engine.
//
// Scrubs sensitive tokens (emails, credit cards, API keys, bearer/JWT tokens,
// IPv4, phone numbers, US-SSN-shaped strings) out of free text *at the boundary*
// before it is logged, cached, or persisted. Runs as a compiled binary so the
// scrub happens on the hot path in a low-level language, not in Python.
//
// Credit-card matches are Luhn-validated to cut false positives. Each redaction
// is replaced with a stable category placeholder, and a per-category count plus
// a content fingerprint is emitted for audit.
#ifndef TRYOPS_REDACTION_HPP
#define TRYOPS_REDACTION_HPP

#include <cstdint>
#include <map>
#include <string>

namespace tryops {

struct RedactionResult {
  std::string redacted;                       // text with sensitive spans masked
  std::map<std::string, int> counts;          // category -> matches redacted
  int total = 0;                              // total redactions
  std::uint64_t input_fingerprint = 0;        // FNV-1a of the raw input
  std::uint64_t output_fingerprint = 0;       // FNV-1a of the redacted output
};

// Redact every supported category from `text`.
RedactionResult redact(const std::string& text);

// Luhn checksum validator (exposed for tests).
bool luhn_valid(const std::string& digits);

// FNV-1a 64-bit hash (stable, dependency-free) for audit fingerprints.
std::uint64_t fnv1a(const std::string& data);

}  // namespace tryops

#endif  // TRYOPS_REDACTION_HPP
