#include "tryops_redaction.hpp"

#include <cstdio>
#include <string>

namespace {

int failures = 0;

void check(bool cond, const char* what) {
  if (!cond) {
    std::printf("FAIL: %s\n", what);
    failures += 1;
  }
}

bool contains(const std::string& hay, const std::string& needle) {
  return hay.find(needle) != std::string::npos;
}

void test_email() {
  auto r = tryops::redact("contact alice@example.com please");
  check(r.counts["email"] == 1, "email count");
  check(contains(r.redacted, "[REDACTED_EMAIL]"), "email placeholder");
  check(!contains(r.redacted, "alice@example.com"), "email removed");
}

void test_secrets() {
  auto r = tryops::redact(
      "key sk-ABCDEFGHIJKLMNOPQRSTUVWX token ghp_ABCDEFGHIJKLMNOPQRST "
      "aws AKIAIOSFODNN7EXAMPLE bearer Bearer abcdef0123456789ABCDEF");
  check(r.counts["api_key"] == 1, "api_key");
  check(r.counts["github_token"] == 1, "github_token");
  check(r.counts["aws_key"] == 1, "aws_key");
  check(r.counts["bearer"] == 1, "bearer");
  check(!contains(r.redacted, "sk-ABCDEF"), "api key removed");
  check(!contains(r.redacted, "AKIAIOSFODNN7EXAMPLE"), "aws key removed");
}

void test_luhn() {
  // 4111111111111111 is a valid Visa test number -> redacted.
  auto good = tryops::redact("card 4111 1111 1111 1111 end");
  check(good.counts["credit_card"] == 1, "valid card redacted");
  // 1234567890123456 fails Luhn -> not a card.
  auto bad = tryops::redact("id 1234567890123456 end");
  check(bad.counts.find("credit_card") == bad.counts.end(), "invalid card kept");
  check(tryops::luhn_valid("4111111111111111"), "luhn valid");
  check(!tryops::luhn_valid("4111111111111112"), "luhn invalid");
}

void test_jwt_and_ip() {
  auto r = tryops::redact(
      "tok eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc-_DEF from 192.168.1.42");
  check(r.counts["jwt"] == 1, "jwt");
  check(r.counts["ipv4"] == 1, "ipv4");
}

void test_clean_text() {
  auto r = tryops::redact("the quick brown fox jumps over the lazy dog");
  check(r.total == 0, "clean text untouched");
  check(r.input_fingerprint == r.output_fingerprint, "fingerprints equal when unchanged");
}

void test_fingerprint_changes() {
  auto r = tryops::redact("email me at bob@corp.io");
  check(r.input_fingerprint != r.output_fingerprint, "fingerprint changes on redaction");
}

}  // namespace

int main() {
  test_email();
  test_secrets();
  test_luhn();
  test_jwt_and_ip();
  test_clean_text();
  test_fingerprint_changes();
  if (failures == 0) {
    std::printf("ok: all redaction tests passed\n");
    return 0;
  }
  std::printf("FAILED: %d redaction checks\n", failures);
  return 1;
}
