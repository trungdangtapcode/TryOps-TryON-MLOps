#include <algorithm>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

struct Finding {
  std::string id;
  std::string severity;
  std::string path;
  std::string message;
};

struct FileReport {
  std::string path;
  std::string extension;
  std::uint64_t size_bytes = 0;
  bool exists = false;
  bool weight_like = false;
  bool safetensors = false;
  bool header_valid = false;
  bool rejected = false;
  std::string classification;
  std::string fingerprint;
};

std::string lower(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  return value;
}

std::string extension_for(const std::string& path) {
  const auto slash = path.find_last_of("/\\");
  const auto dot = path.find_last_of('.');
  if (dot == std::string::npos || (slash != std::string::npos && dot < slash)) {
    return "";
  }
  return lower(path.substr(dot));
}

bool contains(const std::vector<std::string>& values, const std::string& needle) {
  for (const auto& value : values) {
    if (value == needle) {
      return true;
    }
  }
  return false;
}

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

std::string fingerprint_file(const std::string& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return "";
  }
  std::uint64_t hash = 1469598103934665603ULL;
  char buffer[4096];
  while (input.read(buffer, sizeof(buffer)) || input.gcount() > 0) {
    const auto count = input.gcount();
    for (std::streamsize index = 0; index < count; ++index) {
      hash ^= static_cast<unsigned char>(buffer[index]);
      hash *= 1099511628211ULL;
    }
  }
  std::ostringstream out;
  out << "fnv1a64:" << std::hex << std::setw(16) << std::setfill('0') << hash;
  return out.str();
}

bool validate_safetensors_header(const std::string& path, std::uint64_t file_size) {
  if (file_size < 10) {
    return false;
  }
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return false;
  }
  unsigned char header_size_bytes[8] = {};
  input.read(reinterpret_cast<char*>(header_size_bytes), 8);
  if (input.gcount() != 8) {
    return false;
  }
  std::uint64_t header_size = 0;
  for (int index = 0; index < 8; ++index) {
    header_size |= static_cast<std::uint64_t>(header_size_bytes[index]) << (8 * index);
  }
  if (header_size == 0 || header_size > file_size - 8 || header_size > 16 * 1024 * 1024) {
    return false;
  }
  std::string header;
  header.resize(static_cast<std::size_t>(header_size));
  input.read(&header[0], static_cast<std::streamsize>(header.size()));
  if (static_cast<std::uint64_t>(input.gcount()) != header_size) {
    return false;
  }
  const auto first = header.find_first_not_of(" \t\r\n");
  const auto last = header.find_last_not_of(" \t\r\n");
  return first != std::string::npos && last != std::string::npos && header[first] == '{' && header[last] == '}';
}

bool looks_like_pickle_payload(const std::string& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return false;
  }
  std::string sample;
  sample.resize(8192);
  input.read(&sample[0], static_cast<std::streamsize>(sample.size()));
  sample.resize(static_cast<std::size_t>(input.gcount()));
  if (sample.empty()) {
    return false;
  }
  const unsigned char first = static_cast<unsigned char>(sample[0]);
  if (first == 0x80) {
    return true;
  }
  const std::vector<std::string> markers = {
      "GLOBAL", "__reduce__", "builtins", "posix", "nt", "os\nsystem", "subprocess"};
  for (const auto& marker : markers) {
    if (sample.find(marker) != std::string::npos) {
      return true;
    }
  }
  return false;
}

FileReport scan_file(const std::string& path, std::vector<Finding>& findings) {
  static const std::vector<std::string> pickle_like = {
      ".bin", ".pt", ".pth", ".ckpt", ".pkl", ".pickle", ".joblib"};
  static const std::vector<std::string> review_required = {
      ".h5", ".hdf5", ".keras", ".pb", ".onnx", ".tflite"};
  static const std::vector<std::string> safe_non_weight = {
      ".json", ".txt", ".md", ".model", ".vocab", ".merges", ".yaml", ".yml"};

  FileReport report;
  report.path = path;
  report.extension = extension_for(path);
  report.weight_like = report.extension == ".safetensors" || contains(pickle_like, report.extension) ||
                       contains(review_required, report.extension);

  std::ifstream input(path, std::ios::binary | std::ios::ate);
  report.exists = static_cast<bool>(input);
  if (!report.exists) {
    report.rejected = true;
    report.classification = "missing";
    findings.push_back({"MODEL-FILE-MISSING", "critical", path, "model artifact path does not exist"});
    return report;
  }
  report.size_bytes = static_cast<std::uint64_t>(input.tellg());
  report.fingerprint = fingerprint_file(path);

  if (report.extension == ".safetensors") {
    report.safetensors = true;
    report.header_valid = validate_safetensors_header(path, report.size_bytes);
    report.classification = report.header_valid ? "safetensors_weight" : "invalid_safetensors";
    if (!report.header_valid) {
      report.rejected = true;
      findings.push_back({"MODEL-SAFETENSORS-INVALID", "critical", path, "SafeTensors header is invalid"});
    }
    return report;
  }

  if (contains(pickle_like, report.extension)) {
    report.rejected = true;
    report.classification = looks_like_pickle_payload(path) ? "pickle_like_weight" : "blocked_weight_extension";
    findings.push_back({
        "MODEL-PICKLE-FORMAT-BLOCKED",
        "critical",
        path,
        "pickle-family model artifact is blocked by the SafeTensors-only policy"});
    return report;
  }

  if (contains(review_required, report.extension)) {
    report.rejected = true;
    report.classification = "active_or_graph_format_requires_review";
    findings.push_back({
        "MODEL-ACTIVE-FORMAT-REVIEW-REQUIRED",
        "high",
        path,
        "model serialization format requires an explicit scanner allowlist before promotion"});
    return report;
  }

  if (contains(safe_non_weight, report.extension)) {
    report.classification = "safe_support_file";
    return report;
  }

  report.rejected = true;
  report.classification = "unknown_model_artifact";
  findings.push_back({
      "MODEL-UNKNOWN-FORMAT",
      "high",
      path,
      "unknown model artifact extension is rejected until allowlisted"});
  return report;
}

void print_json(const std::vector<FileReport>& files, const std::vector<Finding>& findings) {
  int safetensors_count = 0;
  int unsafe_count = 0;
  int critical = 0;
  int high = 0;
  for (const auto& file : files) {
    if (file.safetensors && file.header_valid) {
      ++safetensors_count;
    }
    if (file.rejected) {
      ++unsafe_count;
    }
  }
  for (const auto& finding : findings) {
    if (finding.severity == "critical") {
      ++critical;
    } else if (finding.severity == "high") {
      ++high;
    }
  }
  const bool passed = !files.empty() && unsafe_count == 0 && safetensors_count > 0;

  std::cout << "{";
  std::cout << "\"schema_version\":\"tryops.native_model_scan.v1\",";
  std::cout << "\"scanner\":{\"name\":\"tryops_model_scan\",\"language\":\"c++\",\"version\":\"0.1.0\"},";
  std::cout << "\"policy\":\"safetensors_only\",";
  std::cout << "\"passed\":" << (passed ? "true" : "false") << ",";
  std::cout << "\"safe_tensors_only\":" << (passed ? "true" : "false") << ",";
  std::cout << "\"file_count\":" << files.size() << ",";
  std::cout << "\"summary\":{";
  std::cout << "\"safetensors_files\":" << safetensors_count << ",";
  std::cout << "\"unsafe_file_count\":" << unsafe_count << ",";
  std::cout << "\"critical\":" << critical << ",";
  std::cout << "\"high\":" << high << ",";
  std::cout << "\"finding_count\":" << findings.size();
  std::cout << "},";
  std::cout << "\"files\":[";
  for (std::size_t index = 0; index < files.size(); ++index) {
    const auto& file = files[index];
    if (index != 0) {
      std::cout << ",";
    }
    std::cout << "{";
    std::cout << "\"path\":\"" << json_escape(file.path) << "\",";
    std::cout << "\"extension\":\"" << json_escape(file.extension) << "\",";
    std::cout << "\"exists\":" << (file.exists ? "true" : "false") << ",";
    std::cout << "\"size_bytes\":" << file.size_bytes << ",";
    std::cout << "\"weight_like\":" << (file.weight_like ? "true" : "false") << ",";
    std::cout << "\"safetensors\":" << (file.safetensors ? "true" : "false") << ",";
    std::cout << "\"header_valid\":" << (file.header_valid ? "true" : "false") << ",";
    std::cout << "\"rejected\":" << (file.rejected ? "true" : "false") << ",";
    std::cout << "\"classification\":\"" << json_escape(file.classification) << "\",";
    std::cout << "\"fingerprint\":\"" << json_escape(file.fingerprint) << "\"";
    std::cout << "}";
  }
  std::cout << "],";
  std::cout << "\"findings\":[";
  for (std::size_t index = 0; index < findings.size(); ++index) {
    const auto& finding = findings[index];
    if (index != 0) {
      std::cout << ",";
    }
    std::cout << "{";
    std::cout << "\"id\":\"" << json_escape(finding.id) << "\",";
    std::cout << "\"severity\":\"" << json_escape(finding.severity) << "\",";
    std::cout << "\"path\":\"" << json_escape(finding.path) << "\",";
    std::cout << "\"message\":\"" << json_escape(finding.message) << "\"";
    std::cout << "}";
  }
  std::cout << "]";
  std::cout << "}\n";
}

}  // namespace

int main(int argc, char** argv) {
  std::vector<std::string> paths;
  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    if (arg == "--help" || arg == "-h") {
      std::cout << "usage: tryops_model_scan_cli <model-file> [model-file...]\n";
      return 0;
    }
    paths.push_back(arg);
  }
  std::vector<Finding> findings;
  std::vector<FileReport> reports;
  for (const auto& path : paths) {
    reports.push_back(scan_file(path, findings));
  }
  if (paths.empty()) {
    findings.push_back({"MODEL-SCAN-NO-FILES", "critical", "", "no model artifact files were provided"});
  }
  print_json(reports, findings);
  return findings.empty() && !reports.empty() ? 0 : 2;
}
