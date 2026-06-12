#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace tryops::gguf_preflight {

struct MetadataEntry {
  std::string key;
  std::string type;
  std::string value;
};

struct TensorPreview {
  std::string name;
  std::vector<std::uint64_t> dimensions;
  std::string type;
  std::uint64_t offset = 0;
};

struct RuntimeInfo {
  std::string llama_cli_path = "llama-cli";
  bool llama_cli_available = false;
  bool generation_tested = false;
};

struct PreflightReport {
  std::string path;
  bool exists = false;
  bool passed = false;
  std::uint64_t size_bytes = 0;
  std::string magic;
  std::uint32_t version = 0;
  std::uint64_t tensor_count = 0;
  std::uint64_t metadata_kv_count = 0;
  std::map<std::string, std::string> selected_metadata;
  std::map<std::string, std::uint64_t> tensor_type_counts;
  std::vector<MetadataEntry> metadata_preview;
  std::vector<TensorPreview> tensor_preview;
  RuntimeInfo runtime;
  std::vector<std::string> reasons;
};

PreflightReport inspect_file(const std::string& path, const std::string& llama_cli_path);
std::string render_json(const PreflightReport& report);

}  // namespace tryops::gguf_preflight
