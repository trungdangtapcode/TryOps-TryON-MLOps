#include "tryops_redaction.hpp"

#include <regex>
#include <utility>
#include <vector>

namespace tryops {
namespace {

// A detector is a pattern, its category label, and whether matched digit-runs
// must pass the Luhn check (credit cards).
struct Detector {
  std::regex pattern;
  std::string category;
  std::string placeholder;
  bool luhn = false;
};

std::string digits_only(const std::string& s) {
  std::string out;
  for (char c : s) {
    if (c >= '0' && c <= '9') {
      out.push_back(c);
    }
  }
  return out;
}

// Order matters: more specific / higher-entropy patterns run first so a secret
// is not partially eaten by a broader detector.
const std::vector<Detector>& detectors() {
  static const std::vector<Detector> kDetectors = [] {
    using std::regex;
    auto opt = std::regex::optimize;
    std::vector<Detector> d;
    // JWT: three base64url segments separated by dots.
    d.push_back({regex(R"(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)", opt),
                 "jwt", "[REDACTED_JWT]", false});
    // AWS access key id.
    d.push_back({regex(R"(AKIA[0-9A-Z]{16})", opt), "aws_key", "[REDACTED_AWS_KEY]", false});
    // GitHub / OpenAI-style tokens.
    d.push_back({regex(R"((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,})", opt),
                 "github_token", "[REDACTED_GITHUB_TOKEN]", false});
    d.push_back({regex(R"(sk-[A-Za-z0-9]{20,})", opt), "api_key", "[REDACTED_API_KEY]", false});
    // Bearer tokens.
    d.push_back({regex(R"([Bb]earer\s+[A-Za-z0-9._-]{16,})", opt),
                 "bearer", "[REDACTED_BEARER]", false});
    // Email addresses.
    d.push_back({regex(R"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", opt),
                 "email", "[REDACTED_EMAIL]", false});
    // Credit-card-shaped 13-16 digit runs (Luhn-validated below).
    d.push_back({regex(R"(\b(?:\d[ -]?){13,19}\b)", opt),
                 "credit_card", "[REDACTED_CC]", true});
    // US-SSN shaped.
    d.push_back({regex(R"(\b\d{3}-\d{2}-\d{4}\b)", opt), "ssn", "[REDACTED_SSN]", false});
    // IPv4 addresses.
    d.push_back({regex(R"(\b(?:\d{1,3}\.){3}\d{1,3}\b)", opt), "ipv4", "[REDACTED_IP]", false});
    // Phone numbers: explicit international (+...), (area) form, or 3-3-4
    // grouped form. Deliberately narrow so ISO dates/timestamps are not matched.
    d.push_back({regex(
                     R"((?:\+\d[\d\s().-]{7,}\d)|(?:\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4})|(?:\b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b))",
                     opt),
                 "phone", "[REDACTED_PHONE]", false});
    return d;
  }();
  return kDetectors;
}

}  // namespace

std::uint64_t fnv1a(const std::string& data) {
  std::uint64_t hash = 1469598103934665603ULL;
  for (unsigned char c : data) {
    hash ^= c;
    hash *= 1099511628211ULL;
  }
  return hash;
}

bool luhn_valid(const std::string& digits) {
  if (digits.size() < 13 || digits.size() > 19) {
    return false;
  }
  int sum = 0;
  bool dbl = false;
  for (auto it = digits.rbegin(); it != digits.rend(); ++it) {
    int n = *it - '0';
    if (dbl) {
      n *= 2;
      if (n > 9) {
        n -= 9;
      }
    }
    sum += n;
    dbl = !dbl;
  }
  return sum % 10 == 0;
}

RedactionResult redact(const std::string& text) {
  RedactionResult result;
  result.input_fingerprint = fnv1a(text);
  std::string current = text;

  for (const auto& det : detectors()) {
    std::string rebuilt;
    rebuilt.reserve(current.size());
    auto begin = std::sregex_iterator(current.begin(), current.end(), det.pattern);
    auto end = std::sregex_iterator();
    std::size_t last = 0;
    for (auto it = begin; it != end; ++it) {
      const std::smatch& m = *it;
      const std::string matched = m.str();

      if (det.luhn && !luhn_valid(digits_only(matched))) {
        continue;  // not a real card number; leave it untouched
      }

      const std::size_t pos = static_cast<std::size_t>(m.position());
      rebuilt.append(current, last, pos - last);
      rebuilt.append(det.placeholder);
      last = pos + matched.size();

      result.counts[det.category] += 1;
      result.total += 1;
    }
    rebuilt.append(current, last, current.size() - last);
    current = std::move(rebuilt);
  }

  result.redacted = current;
  result.output_fingerprint = fnv1a(current);
  return result;
}

}  // namespace tryops
