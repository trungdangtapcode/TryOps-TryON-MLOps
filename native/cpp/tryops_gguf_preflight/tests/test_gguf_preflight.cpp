#include "tryops_gguf_preflight.hpp"

#include <cassert>
#include <cstdint>
#include <fstream>
#include <string>
#include <vector>

namespace {

void write_u32(std::ofstream& out, std::uint32_t value) {
  for (int index = 0; index < 4; ++index) {
    out.put(static_cast<char>((value >> (8 * index)) & 0xff));
  }
}

void write_u64(std::ofstream& out, std::uint64_t value) {
  for (int index = 0; index < 8; ++index) {
    out.put(static_cast<char>((value >> (8 * index)) & 0xff));
  }
}

void write_string(std::ofstream& out, const std::string& value) {
  write_u64(out, value.size());
  out.write(value.data(), static_cast<std::streamsize>(value.size()));
}

void write_metadata_string(std::ofstream& out, const std::string& key, const std::string& value) {
  write_string(out, key);
  write_u32(out, 8);
  write_string(out, value);
}

void write_metadata_u32(std::ofstream& out, const std::string& key, std::uint32_t value) {
  write_string(out, key);
  write_u32(out, 4);
  write_u32(out, value);
}

void write_fixture(const std::string& path) {
  std::ofstream out(path, std::ios::binary);
  out.write("GGUF", 4);
  write_u32(out, 3);
  write_u64(out, 1);
  write_u64(out, 5);

  write_metadata_string(out, "general.architecture", "smollm2");
  write_metadata_string(out, "general.name", "TryOps fixture");
  write_metadata_u32(out, "general.file_type", 10);
  write_metadata_u32(out, "smollm2.context_length", 2048);
  write_metadata_string(out, "tokenizer.ggml.model", "gpt2");

  write_string(out, "blk.0.attn_q.weight");
  write_u32(out, 2);
  write_u64(out, 16);
  write_u64(out, 16);
  write_u32(out, 10);
  write_u64(out, 0);
  out.write("GGUFTENSORPAYLOAD", 17);
}

}  // namespace

int main() {
  const std::string path = "/tmp/tryops_gguf_preflight_fixture.gguf";
  write_fixture(path);

  const auto report = tryops::gguf_preflight::inspect_file(path, "definitely-not-llama-cli");
  assert(report.passed);
  assert(report.magic == "GGUF");
  assert(report.version == 3);
  assert(report.tensor_count == 1);
  assert(report.metadata_kv_count == 5);
  assert(report.selected_metadata.at("general.architecture") == "smollm2");
  assert(report.selected_metadata.at("general.file_type_name") == "mostly_q2_k");
  assert(report.tensor_type_counts.at("Q2_K") == 1);
  assert(!report.runtime.llama_cli_available);

  const auto body = tryops::gguf_preflight::render_json(report);
  assert(body.find("\"schema_version\":\"tryops.native_gguf_preflight.v1\"") != std::string::npos);
  assert(body.find("\"general.architecture\":\"smollm2\"") != std::string::npos);
  assert(body.find("\"Q2_K\":1") != std::string::npos);
  return 0;
}
