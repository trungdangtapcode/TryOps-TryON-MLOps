#include "tryops_gguf_preflight.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <unistd.h>

namespace tryops::gguf_preflight {
namespace {

constexpr std::uint64_t kMaxPreviewEntries = 32;
constexpr std::uint64_t kMaxTensorPreview = 12;
constexpr std::uint64_t kMaxStringBytes = 16 * 1024 * 1024;
constexpr std::uint64_t kMaxArrayItemsToSkip = 200000000ULL;

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    switch (ch) {
      case '\\':
        out << "\\\\";
        break;
      case '"':
        out << "\\\"";
        break;
      case '\n':
        out << "\\n";
        break;
      case '\r':
        out << "\\r";
        break;
      case '\t':
        out << "\\t";
        break;
      default:
        if (static_cast<unsigned char>(ch) < 0x20) {
          out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
              << static_cast<int>(static_cast<unsigned char>(ch));
        } else {
          out << ch;
        }
        break;
    }
  }
  return out.str();
}

template <typename T>
bool read_le(std::ifstream& input, T& value) {
  std::array<unsigned char, sizeof(T)> bytes{};
  input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
  if (input.gcount() != static_cast<std::streamsize>(bytes.size())) {
    return false;
  }
  value = 0;
  for (std::size_t index = 0; index < bytes.size(); ++index) {
    value |= static_cast<T>(bytes[index]) << (8 * index);
  }
  return true;
}

bool read_float32(std::ifstream& input, float& value) {
  std::uint32_t raw = 0;
  if (!read_le(input, raw)) {
    return false;
  }
  std::memcpy(&value, &raw, sizeof(value));
  return true;
}

bool read_float64(std::ifstream& input, double& value) {
  std::uint64_t raw = 0;
  if (!read_le(input, raw)) {
    return false;
  }
  std::memcpy(&value, &raw, sizeof(value));
  return true;
}

bool read_string(std::ifstream& input, std::string& value) {
  std::uint64_t size = 0;
  if (!read_le(input, size) || size > kMaxStringBytes) {
    return false;
  }
  value.assign(static_cast<std::size_t>(size), '\0');
  if (size == 0) {
    return true;
  }
  input.read(value.data(), static_cast<std::streamsize>(value.size()));
  return input.gcount() == static_cast<std::streamsize>(value.size());
}

std::string value_type_name(std::uint32_t type) {
  switch (type) {
    case 0:
      return "uint8";
    case 1:
      return "int8";
    case 2:
      return "uint16";
    case 3:
      return "int16";
    case 4:
      return "uint32";
    case 5:
      return "int32";
    case 6:
      return "float32";
    case 7:
      return "bool";
    case 8:
      return "string";
    case 9:
      return "array";
    case 10:
      return "uint64";
    case 11:
      return "int64";
    case 12:
      return "float64";
    default:
      return "unknown_" + std::to_string(type);
  }
}

std::string tensor_type_name(std::uint32_t type) {
  switch (type) {
    case 0:
      return "F32";
    case 1:
      return "F16";
    case 2:
      return "Q4_0";
    case 3:
      return "Q4_1";
    case 6:
      return "Q5_0";
    case 7:
      return "Q5_1";
    case 8:
      return "Q8_0";
    case 9:
      return "Q8_1";
    case 10:
      return "Q2_K";
    case 11:
      return "Q3_K";
    case 12:
      return "Q4_K";
    case 13:
      return "Q5_K";
    case 14:
      return "Q6_K";
    case 15:
      return "Q8_K";
    case 16:
      return "IQ2_XXS";
    case 17:
      return "IQ2_XS";
    case 18:
      return "IQ3_XXS";
    case 19:
      return "IQ1_S";
    case 20:
      return "IQ4_NL";
    case 21:
      return "IQ3_S";
    case 22:
      return "IQ2_S";
    case 23:
      return "IQ4_XS";
    case 24:
      return "I8";
    case 25:
      return "I16";
    case 26:
      return "I32";
    case 27:
      return "I64";
    case 28:
      return "F64";
    case 29:
      return "IQ1_M";
    case 30:
      return "BF16";
    default:
      return "TYPE_" + std::to_string(type);
  }
}

std::string file_type_name(const std::string& value) {
  if (value == "0") return "all_f32";
  if (value == "1") return "mostly_f16";
  if (value == "2") return "mostly_q4_0";
  if (value == "3") return "mostly_q4_1";
  if (value == "7") return "mostly_q8_0";
  if (value == "10") return "mostly_q2_k";
  if (value == "11") return "mostly_q3_k_s";
  if (value == "12") return "mostly_q3_k_m";
  if (value == "13") return "mostly_q3_k_l";
  if (value == "14") return "mostly_q4_k_s";
  if (value == "15") return "mostly_q4_k_m";
  if (value == "16") return "mostly_q5_k_s";
  if (value == "17") return "mostly_q5_k_m";
  if (value == "18") return "mostly_q6_k";
  return "";
}

std::string scalar_to_string(bool value) { return value ? "true" : "false"; }

template <typename T>
std::string number_to_string(T value) {
  std::ostringstream out;
  out << value;
  return out.str();
}

bool skip_value(std::ifstream& input, std::uint32_t type);

bool read_value_summary(std::ifstream& input, std::uint32_t type, std::string& summary) {
  switch (type) {
    case 0: {
      std::uint8_t value = 0;
      if (!read_le(input, value)) return false;
      summary = number_to_string(static_cast<unsigned int>(value));
      return true;
    }
    case 1: {
      std::uint8_t raw = 0;
      if (!read_le(input, raw)) return false;
      summary = number_to_string(static_cast<int>(static_cast<std::int8_t>(raw)));
      return true;
    }
    case 2: {
      std::uint16_t value = 0;
      if (!read_le(input, value)) return false;
      summary = number_to_string(value);
      return true;
    }
    case 3: {
      std::uint16_t raw = 0;
      if (!read_le(input, raw)) return false;
      summary = number_to_string(static_cast<std::int16_t>(raw));
      return true;
    }
    case 4: {
      std::uint32_t value = 0;
      if (!read_le(input, value)) return false;
      summary = number_to_string(value);
      return true;
    }
    case 5: {
      std::uint32_t raw = 0;
      if (!read_le(input, raw)) return false;
      summary = number_to_string(static_cast<std::int32_t>(raw));
      return true;
    }
    case 6: {
      float value = 0.0F;
      if (!read_float32(input, value)) return false;
      summary = number_to_string(value);
      return true;
    }
    case 7: {
      std::uint8_t value = 0;
      if (!read_le(input, value)) return false;
      summary = scalar_to_string(value != 0);
      return true;
    }
    case 8:
      return read_string(input, summary);
    case 9: {
      std::uint32_t item_type = 0;
      std::uint64_t item_count = 0;
      if (!read_le(input, item_type) || !read_le(input, item_count)) return false;
      if (item_count > kMaxArrayItemsToSkip) return false;
      for (std::uint64_t index = 0; index < item_count; ++index) {
        if (!skip_value(input, item_type)) return false;
      }
      summary = "array<" + value_type_name(item_type) + ">[" + std::to_string(item_count) + "]";
      return true;
    }
    case 10: {
      std::uint64_t value = 0;
      if (!read_le(input, value)) return false;
      summary = number_to_string(value);
      return true;
    }
    case 11: {
      std::uint64_t raw = 0;
      if (!read_le(input, raw)) return false;
      summary = number_to_string(static_cast<std::int64_t>(raw));
      return true;
    }
    case 12: {
      double value = 0.0;
      if (!read_float64(input, value)) return false;
      summary = number_to_string(value);
      return true;
    }
    default:
      return false;
  }
}

bool skip_value(std::ifstream& input, std::uint32_t type) {
  std::string ignored;
  return read_value_summary(input, type, ignored);
}

bool on_path(const std::string& candidate) {
  if (candidate.find('/') != std::string::npos) {
    return access(candidate.c_str(), X_OK) == 0;
  }
  const char* path_env = std::getenv("PATH");
  if (path_env == nullptr) {
    return false;
  }
  std::stringstream paths(path_env);
  std::string dir;
  while (std::getline(paths, dir, ':')) {
    if (dir.empty()) {
      dir = ".";
    }
    const std::string full = dir + "/" + candidate;
    if (access(full.c_str(), X_OK) == 0) {
      return true;
    }
  }
  return false;
}

void add_selected_metadata(PreflightReport& report, const std::string& key, const std::string& value) {
  static const std::vector<std::string> exact = {
      "general.architecture", "general.name", "general.file_type", "general.quantization_version",
      "tokenizer.ggml.model"};
  if (std::find(exact.begin(), exact.end(), key) != exact.end() ||
      key.find(".context_length") != std::string::npos ||
      key.find(".embedding_length") != std::string::npos ||
      key.find(".block_count") != std::string::npos) {
    report.selected_metadata[key] = value;
  }
}

}  // namespace

PreflightReport inspect_file(const std::string& path, const std::string& llama_cli_path) {
  PreflightReport report;
  report.path = path;
  report.runtime.llama_cli_path = llama_cli_path.empty() ? "llama-cli" : llama_cli_path;
  report.runtime.llama_cli_available = on_path(report.runtime.llama_cli_path);

  std::ifstream input(path, std::ios::binary | std::ios::ate);
  report.exists = static_cast<bool>(input);
  if (!report.exists) {
    report.reasons.push_back("GGUF file is missing");
    return report;
  }
  report.size_bytes = static_cast<std::uint64_t>(input.tellg());
  input.seekg(0);

  char magic[4] = {};
  input.read(magic, 4);
  if (input.gcount() != 4) {
    report.reasons.push_back("file is too small for GGUF header");
    return report;
  }
  report.magic.assign(magic, 4);
  if (report.magic != "GGUF") {
    report.reasons.push_back("magic header is not GGUF");
    return report;
  }
  if (!read_le(input, report.version) || !read_le(input, report.tensor_count) ||
      !read_le(input, report.metadata_kv_count)) {
    report.reasons.push_back("failed to read GGUF version/count header");
    return report;
  }
  if (report.version == 0 || report.version > 4) {
    report.reasons.push_back("GGUF version is unsupported or suspicious");
  }
  if (report.tensor_count == 0) {
    report.reasons.push_back("GGUF tensor_count is zero");
  }
  if (report.metadata_kv_count == 0) {
    report.reasons.push_back("GGUF metadata_kv_count is zero");
  }

  for (std::uint64_t index = 0; index < report.metadata_kv_count; ++index) {
    std::string key;
    std::uint32_t type = 0;
    std::string value;
    if (!read_string(input, key) || !read_le(input, type) || !read_value_summary(input, type, value)) {
      report.reasons.push_back("failed to parse GGUF metadata entry " + std::to_string(index));
      return report;
    }
    add_selected_metadata(report, key, value);
    if (report.metadata_preview.size() < kMaxPreviewEntries) {
      report.metadata_preview.push_back({key, value_type_name(type), value});
    }
  }

  for (std::uint64_t index = 0; index < report.tensor_count; ++index) {
    std::string name;
    std::uint32_t n_dimensions = 0;
    if (!read_string(input, name) || !read_le(input, n_dimensions) || n_dimensions > 8) {
      report.reasons.push_back("failed to parse GGUF tensor header " + std::to_string(index));
      return report;
    }
    TensorPreview tensor;
    tensor.name = name;
    for (std::uint32_t dim = 0; dim < n_dimensions; ++dim) {
      std::uint64_t size = 0;
      if (!read_le(input, size)) {
        report.reasons.push_back("failed to parse GGUF tensor dimensions");
        return report;
      }
      tensor.dimensions.push_back(size);
    }
    std::uint32_t tensor_type = 0;
    if (!read_le(input, tensor_type) || !read_le(input, tensor.offset)) {
      report.reasons.push_back("failed to parse GGUF tensor type/offset");
      return report;
    }
    tensor.type = tensor_type_name(tensor_type);
    report.tensor_type_counts[tensor.type] += 1;
    if (report.tensor_preview.size() < kMaxTensorPreview) {
      report.tensor_preview.push_back(tensor);
    }
  }

  const auto file_type = report.selected_metadata.find("general.file_type");
  if (file_type != report.selected_metadata.end()) {
    const std::string type_name = file_type_name(file_type->second);
    if (!type_name.empty()) {
      report.selected_metadata["general.file_type_name"] = type_name;
    }
  }
  if (!report.runtime.llama_cli_available) {
    report.reasons.push_back("llama.cpp CLI is not installed; generation smoke was not run");
  }
  report.passed = report.magic == "GGUF" && report.version > 0 && report.version <= 4 &&
                  report.tensor_count > 0 && report.metadata_kv_count > 0 &&
                  !report.tensor_type_counts.empty();
  return report;
}

std::string render_json(const PreflightReport& report) {
  std::ostringstream out;
  out << "{";
  out << "\"schema_version\":\"tryops.native_gguf_preflight.v1\",";
  out << "\"engine\":{\"name\":\"tryops_gguf_preflight\",\"language\":\"cpp\",\"version\":\"0.1.0\"},";
  out << "\"passed\":" << (report.passed ? "true" : "false") << ",";
  out << "\"path\":\"" << json_escape(report.path) << "\",";
  out << "\"exists\":" << (report.exists ? "true" : "false") << ",";
  out << "\"size_bytes\":" << report.size_bytes << ",";
  out << "\"header\":{\"magic\":\"" << json_escape(report.magic) << "\",";
  out << "\"version\":" << report.version << ",";
  out << "\"tensor_count\":" << report.tensor_count << ",";
  out << "\"metadata_kv_count\":" << report.metadata_kv_count << "},";
  out << "\"selected_metadata\":{";
  bool first = true;
  for (const auto& [key, value] : report.selected_metadata) {
    if (!first) out << ",";
    first = false;
    out << "\"" << json_escape(key) << "\":\"" << json_escape(value) << "\"";
  }
  out << "},";
  out << "\"tensor_type_counts\":{";
  first = true;
  for (const auto& [key, value] : report.tensor_type_counts) {
    if (!first) out << ",";
    first = false;
    out << "\"" << json_escape(key) << "\":" << value;
  }
  out << "},";
  out << "\"metadata_preview\":[";
  for (std::size_t index = 0; index < report.metadata_preview.size(); ++index) {
    const auto& entry = report.metadata_preview[index];
    if (index > 0) out << ",";
    out << "{\"key\":\"" << json_escape(entry.key) << "\",";
    out << "\"type\":\"" << json_escape(entry.type) << "\",";
    out << "\"value\":\"" << json_escape(entry.value) << "\"}";
  }
  out << "],";
  out << "\"tensor_preview\":[";
  for (std::size_t index = 0; index < report.tensor_preview.size(); ++index) {
    const auto& tensor = report.tensor_preview[index];
    if (index > 0) out << ",";
    out << "{\"name\":\"" << json_escape(tensor.name) << "\",";
    out << "\"dimensions\":[";
    for (std::size_t dim = 0; dim < tensor.dimensions.size(); ++dim) {
      if (dim > 0) out << ",";
      out << tensor.dimensions[dim];
    }
    out << "],\"type\":\"" << json_escape(tensor.type) << "\",";
    out << "\"offset\":" << tensor.offset << "}";
  }
  out << "],";
  out << "\"runtime\":{\"llama_cli_path\":\"" << json_escape(report.runtime.llama_cli_path) << "\",";
  out << "\"llama_cli_available\":" << (report.runtime.llama_cli_available ? "true" : "false") << ",";
  out << "\"generation_tested\":" << (report.runtime.generation_tested ? "true" : "false") << "},";
  out << "\"reasons\":[";
  for (std::size_t index = 0; index < report.reasons.size(); ++index) {
    if (index > 0) out << ",";
    out << "\"" << json_escape(report.reasons[index]) << "\"";
  }
  out << "]}";
  return out.str();
}

}  // namespace tryops::gguf_preflight
