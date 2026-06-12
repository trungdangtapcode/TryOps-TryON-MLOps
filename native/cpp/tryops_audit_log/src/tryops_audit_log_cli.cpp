// Reads audit payloads (one per stdin line), builds the tamper-evident log, and
// emits a JSON summary: size, Merkle root, chain head, chain-valid flag. With
// --prove <index> it also emits an inclusion proof and its verification result.
// Exit code: 0 if the chain verifies (and any requested proof verifies), 2 else.
#include "tryops_audit_log.hpp"

#include <iostream>
#include <sstream>
#include <string>

int main(int argc, char** argv) {
  long prove_index = -1;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--prove" && i + 1 < argc) {
      prove_index = std::atol(argv[++i]);
    }
  }

  tryops::AuditLog log;
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.empty()) {
      continue;
    }
    // allow an optional "entry=" prefix for symmetry with other engines
    if (line.rfind("entry=", 0) == 0) {
      line = line.substr(6);
    }
    log.append(line);
  }

  const std::string root = log.merkle_root();
  const bool chain_ok = log.verify_chain();
  bool proof_ok = true;

  std::cout << "{";
  std::cout << "\"size\":" << log.size() << ",";
  std::cout << "\"merkle_root\":\"" << root << "\",";
  std::cout << "\"chain_head\":\"" << log.chain_head() << "\",";
  std::cout << "\"chain_valid\":" << (chain_ok ? "true" : "false");

  if (prove_index >= 0 && static_cast<std::size_t>(prove_index) < log.size()) {
    const tryops::InclusionProof proof =
        log.prove(static_cast<std::size_t>(prove_index));
    proof_ok = tryops::verify_inclusion(proof, root);
    std::cout << ",\"proof\":{";
    std::cout << "\"index\":" << proof.index << ",";
    std::cout << "\"tree_size\":" << proof.tree_size << ",";
    std::cout << "\"leaf_hash\":\"" << proof.leaf_hash << "\",";
    std::cout << "\"path_len\":" << proof.siblings.size() << ",";
    std::cout << "\"verified\":" << (proof_ok ? "true" : "false");
    std::cout << "}";
  }

  std::cout << "}\n";
  return (chain_ok && proof_ok) ? 0 : 2;
}
