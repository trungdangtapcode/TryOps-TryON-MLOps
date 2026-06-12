// TryOps native tamper-evident audit log.
//
// Maintains an append-only, hash-chained ledger of audit entries and a Merkle
// tree over them. Any modification to a past entry changes the Merkle root and
// breaks the hash chain, so tampering is detectable with a single root compare
// plus O(log n) inclusion proofs. SHA-256 is implemented from scratch (no
// external deps) so the engine is self-contained on the production boundary; it
// is verified bit-for-bit against Python's hashlib in the test suite.
#ifndef TRYOPS_AUDIT_LOG_HPP
#define TRYOPS_AUDIT_LOG_HPP

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace tryops {

// 32-byte SHA-256 digest rendered as lowercase hex.
std::string sha256_hex(const std::string& data);

struct AuditEntry {
  std::string payload;    // opaque audit record (e.g. a decision JSON)
  std::string leaf_hash;  // sha256(payload)
  std::string chain_hash; // sha256(prev_chain_hash + leaf_hash)
};

struct InclusionProof {
  std::size_t index = 0;
  std::size_t tree_size = 0;
  std::string leaf_hash;
  // ordered sibling hashes from leaf to root, each tagged left/right
  std::vector<std::pair<std::string, bool>> siblings;  // bool: sibling_is_right
  std::string root;
};

class AuditLog {
 public:
  // Append a record; returns its index.
  std::size_t append(const std::string& payload);

  std::size_t size() const { return entries_.size(); }
  const AuditEntry& entry(std::size_t i) const { return entries_.at(i); }
  const std::string& chain_head() const { return chain_head_; }

  // Merkle root over all leaf hashes (empty-tree root is sha256("")).
  std::string merkle_root() const;

  // Proof that entry `index` is included under the current root.
  InclusionProof prove(std::size_t index) const;

  // Recompute the chain from scratch and confirm it matches stored chain hashes
  // — detects any in-place mutation of a past entry.
  bool verify_chain() const;

 private:
  std::vector<AuditEntry> entries_;
  std::string chain_head_;  // sha256 of the whole chain so far
};

// Verify an inclusion proof against an expected root. Pure function.
bool verify_inclusion(const InclusionProof& proof, const std::string& expected_root);

}  // namespace tryops

#endif  // TRYOPS_AUDIT_LOG_HPP
