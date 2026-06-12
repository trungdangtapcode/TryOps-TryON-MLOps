#include "tryops_audit_log.hpp"

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

// Known-answer tests against the SHA-256 spec / standard vectors.
void test_sha256_kat() {
  check(tryops::sha256_hex("") ==
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "sha256 empty");
  check(tryops::sha256_hex("abc") ==
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "sha256 abc");
  check(tryops::sha256_hex(
            "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq") ==
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
        "sha256 56-byte vector");
}

void test_root_and_proofs() {
  tryops::AuditLog log;
  for (int i = 0; i < 5; ++i) {
    log.append("decision-" + std::to_string(i));
  }
  check(log.size() == 5, "size");
  const std::string root = log.merkle_root();
  check(root.size() == 64, "root is 32-byte hex");
  check(log.verify_chain(), "chain valid after append");

  // every leaf has a verifiable inclusion proof
  for (std::size_t i = 0; i < log.size(); ++i) {
    auto proof = log.prove(i);
    check(tryops::verify_inclusion(proof, root), "inclusion proof verifies");
  }
  // a proof must NOT verify against a different root
  auto p = log.prove(2);
  check(!tryops::verify_inclusion(p, tryops::sha256_hex("not-the-root")),
        "proof rejects wrong root");
}

void test_tamper_detection() {
  tryops::AuditLog clean;
  clean.append("a");
  clean.append("b");
  clean.append("c");
  const std::string clean_root = clean.merkle_root();

  // a log with a tampered middle entry yields a different root
  tryops::AuditLog tampered;
  tampered.append("a");
  tampered.append("b-MUTATED");
  tampered.append("c");
  check(tampered.merkle_root() != clean_root, "tamper changes merkle root");
  // the tampered log's own chain is internally consistent (attacker recomputed),
  // but it cannot match the independently published clean root — that's the
  // point of anchoring the root externally.
  check(tampered.verify_chain(), "recomputed chain self-consistent");
}

void test_determinism() {
  tryops::AuditLog a;
  tryops::AuditLog b;
  for (int i = 0; i < 8; ++i) {
    a.append("e" + std::to_string(i));
    b.append("e" + std::to_string(i));
  }
  check(a.merkle_root() == b.merkle_root(), "deterministic root");
  check(a.chain_head() == b.chain_head(), "deterministic chain head");
}

}  // namespace

int main() {
  test_sha256_kat();
  test_root_and_proofs();
  test_tamper_detection();
  test_determinism();
  if (failures == 0) {
    std::printf("ok: all audit_log tests passed\n");
    return 0;
  }
  std::printf("FAILED: %d audit_log checks\n", failures);
  return 1;
}
