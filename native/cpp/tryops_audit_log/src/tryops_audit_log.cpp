#include "tryops_audit_log.hpp"

#include <cstring>

namespace tryops {
namespace {

// ---- SHA-256 (FIPS 180-4), self-contained ----

inline std::uint32_t rotr(std::uint32_t x, std::uint32_t n) {
  return (x >> n) | (x << (32 - n));
}

const std::uint32_t kK[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

std::array<std::uint8_t, 32> sha256(const std::string& msg) {
  std::uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};

  std::vector<std::uint8_t> data(msg.begin(), msg.end());
  const std::uint64_t bit_len = static_cast<std::uint64_t>(data.size()) * 8;
  data.push_back(0x80);
  while (data.size() % 64 != 56) {
    data.push_back(0x00);
  }
  for (int i = 7; i >= 0; --i) {
    data.push_back(static_cast<std::uint8_t>((bit_len >> (i * 8)) & 0xff));
  }

  for (std::size_t chunk = 0; chunk < data.size(); chunk += 64) {
    std::uint32_t w[64];
    for (int i = 0; i < 16; ++i) {
      w[i] = (static_cast<std::uint32_t>(data[chunk + i * 4]) << 24) |
             (static_cast<std::uint32_t>(data[chunk + i * 4 + 1]) << 16) |
             (static_cast<std::uint32_t>(data[chunk + i * 4 + 2]) << 8) |
             (static_cast<std::uint32_t>(data[chunk + i * 4 + 3]));
    }
    for (int i = 16; i < 64; ++i) {
      const std::uint32_t s0 =
          rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
      const std::uint32_t s1 =
          rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
      w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }

    std::uint32_t a = h[0], b = h[1], c = h[2], d = h[3];
    std::uint32_t e = h[4], f = h[5], g = h[6], hh = h[7];
    for (int i = 0; i < 64; ++i) {
      const std::uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const std::uint32_t ch = (e & f) ^ (~e & g);
      const std::uint32_t t1 = hh + S1 + ch + kK[i] + w[i];
      const std::uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
      const std::uint32_t t2 = S0 + maj;
      hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d;
    h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
  }

  std::array<std::uint8_t, 32> out{};
  for (int i = 0; i < 8; ++i) {
    out[i * 4 + 0] = static_cast<std::uint8_t>((h[i] >> 24) & 0xff);
    out[i * 4 + 1] = static_cast<std::uint8_t>((h[i] >> 16) & 0xff);
    out[i * 4 + 2] = static_cast<std::uint8_t>((h[i] >> 8) & 0xff);
    out[i * 4 + 3] = static_cast<std::uint8_t>(h[i] & 0xff);
  }
  return out;
}

std::string to_hex(const std::array<std::uint8_t, 32>& bytes) {
  static const char* digits = "0123456789abcdef";
  std::string out;
  out.reserve(64);
  for (std::uint8_t b : bytes) {
    out.push_back(digits[b >> 4]);
    out.push_back(digits[b & 0x0f]);
  }
  return out;
}

}  // namespace

std::string sha256_hex(const std::string& data) { return to_hex(sha256(data)); }

std::size_t AuditLog::append(const std::string& payload) {
  AuditEntry e;
  e.payload = payload;
  e.leaf_hash = sha256_hex(payload);
  e.chain_hash = sha256_hex(chain_head_ + e.leaf_hash);
  chain_head_ = e.chain_hash;
  entries_.push_back(e);
  return entries_.size() - 1;
}

std::string AuditLog::merkle_root() const {
  if (entries_.empty()) {
    return sha256_hex("");
  }
  std::vector<std::string> level;
  level.reserve(entries_.size());
  for (const auto& e : entries_) {
    level.push_back(e.leaf_hash);
  }
  while (level.size() > 1) {
    std::vector<std::string> next;
    next.reserve((level.size() + 1) / 2);
    for (std::size_t i = 0; i < level.size(); i += 2) {
      if (i + 1 < level.size()) {
        next.push_back(sha256_hex(level[i] + level[i + 1]));
      } else {
        // odd node is promoted (hashed with itself) — RFC 6962 style duplication
        next.push_back(sha256_hex(level[i] + level[i]));
      }
    }
    level = std::move(next);
  }
  return level.front();
}

InclusionProof AuditLog::prove(std::size_t index) const {
  InclusionProof proof;
  proof.index = index;
  proof.tree_size = entries_.size();
  proof.root = merkle_root();
  if (index >= entries_.size()) {
    return proof;
  }
  proof.leaf_hash = entries_[index].leaf_hash;

  std::vector<std::string> level;
  for (const auto& e : entries_) {
    level.push_back(e.leaf_hash);
  }
  std::size_t idx = index;
  while (level.size() > 1) {
    std::vector<std::string> next;
    for (std::size_t i = 0; i < level.size(); i += 2) {
      const std::string& left = level[i];
      const std::string& right = (i + 1 < level.size()) ? level[i + 1] : level[i];
      if (i == idx || i + 1 == idx) {
        const bool sibling_is_right = (idx % 2 == 0);
        const std::string& sibling = sibling_is_right ? right : left;
        proof.siblings.emplace_back(sibling, sibling_is_right);
      }
      next.push_back(sha256_hex(left + right));
    }
    idx /= 2;
    level = std::move(next);
  }
  return proof;
}

bool AuditLog::verify_chain() const {
  std::string head;
  for (const auto& e : entries_) {
    if (sha256_hex(e.payload) != e.leaf_hash) {
      return false;
    }
    head = sha256_hex(head + e.leaf_hash);
    if (head != e.chain_hash) {
      return false;
    }
  }
  return head == chain_head_;
}

bool verify_inclusion(const InclusionProof& proof, const std::string& expected_root) {
  std::string computed = proof.leaf_hash;
  for (const auto& sib : proof.siblings) {
    if (sib.second) {  // sibling on the right -> computed is left
      computed = sha256_hex(computed + sib.first);
    } else {
      computed = sha256_hex(sib.first + computed);
    }
  }
  return computed == expected_root && expected_root == proof.root;
}

}  // namespace tryops
