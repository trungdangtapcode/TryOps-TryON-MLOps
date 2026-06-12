#include <algorithm>
#include <cctype>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::string read_file(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    return "";
  }
  std::ostringstream out;
  out << input.rdbuf();
  return out.str();
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
          out << ' ';
        } else {
          out << ch;
        }
        break;
    }
  }
  return out.str();
}

std::string extract_string_after(const std::string& text, const std::string& key, std::size_t start = 0) {
  const auto key_pos = text.find("\"" + key + "\"", start);
  if (key_pos == std::string::npos) {
    return "";
  }
  const auto colon = text.find(':', key_pos);
  if (colon == std::string::npos) {
    return "";
  }
  auto quote = text.find('"', colon + 1);
  if (quote == std::string::npos) {
    return "";
  }
  std::string value;
  bool escaped = false;
  for (std::size_t index = quote + 1; index < text.size(); ++index) {
    const char ch = text[index];
    if (escaped) {
      value.push_back(ch);
      escaped = false;
      continue;
    }
    if (ch == '\\') {
      escaped = true;
      continue;
    }
    if (ch == '"') {
      return value;
    }
    value.push_back(ch);
  }
  return "";
}

bool contains(const std::vector<std::string>& values, const std::string& needle) {
  return std::find(values.begin(), values.end(), needle) != values.end();
}

bool uuid_shaped(const std::string& value) {
  if (value.size() != 36) {
    return false;
  }
  for (std::size_t index = 0; index < value.size(); ++index) {
    const char ch = value[index];
    if (index == 8 || index == 13 || index == 18 || index == 23) {
      if (ch != '-') {
        return false;
      }
    } else if (!std::isxdigit(static_cast<unsigned char>(ch))) {
      return false;
    }
  }
  return true;
}

int count_occurrences(const std::string& text, const std::string& needle) {
  int count = 0;
  std::size_t pos = 0;
  while ((pos = text.find(needle, pos)) != std::string::npos) {
    ++count;
    pos += needle.size();
  }
  return count;
}

void emit_report(
    bool passed,
    const std::string& event_type,
    const std::string& run_id,
    const std::string& job_namespace,
    const std::string& job_name,
    int input_count,
    int output_count,
    const std::vector<std::string>& reasons) {
  std::cout << "{";
  std::cout << "\"schema_version\":\"tryops.native_openlineage.v1\",";
  std::cout << "\"engine\":{\"name\":\"tryops_openlineage\",\"language\":\"cpp\",\"version\":\"0.1.0\"},";
  std::cout << "\"passed\":" << (passed ? "true" : "false") << ",";
  std::cout << "\"event_type\":\"" << json_escape(event_type) << "\",";
  std::cout << "\"run_id\":\"" << json_escape(run_id) << "\",";
  std::cout << "\"job_namespace\":\"" << json_escape(job_namespace) << "\",";
  std::cout << "\"job_name\":\"" << json_escape(job_name) << "\",";
  std::cout << "\"input_dataset_count\":" << input_count << ",";
  std::cout << "\"output_dataset_count\":" << output_count << ",";
  std::cout << "\"reasons\":[";
  for (std::size_t index = 0; index < reasons.size(); ++index) {
    if (index > 0) {
      std::cout << ",";
    }
    std::cout << "\"" << json_escape(reasons[index]) << "\"";
  }
  std::cout << "]}";
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "usage: tryops_openlineage_cli <openlineage_run_event.json>\n";
    return 1;
  }

  const std::string payload = read_file(argv[1]);
  if (payload.empty()) {
    emit_report(false, "", "", "", "", 0, 0, {"event file is missing or empty"});
    return 2;
  }

  const std::string event_type = extract_string_after(payload, "eventType");
  const std::string event_time = extract_string_after(payload, "eventTime");
  const std::string run_id = extract_string_after(payload, "runId");
  const auto job_pos = payload.find("\"job\"");
  const std::string job_namespace = job_pos == std::string::npos ? "" : extract_string_after(payload, "namespace", job_pos);
  const std::string job_name = job_pos == std::string::npos ? "" : extract_string_after(payload, "name", job_pos);
  const std::string producer = extract_string_after(payload, "producer");
  const std::string schema_url = extract_string_after(payload, "schemaURL");

  std::vector<std::string> reasons;
  const std::vector<std::string> allowed_events = {"START", "RUNNING", "COMPLETE", "ABORT", "FAIL", "OTHER"};
  if (!contains(allowed_events, event_type)) {
    reasons.push_back("eventType is missing or not an OpenLineage run state");
  }
  if (event_time.empty() || event_time.find('T') == std::string::npos) {
    reasons.push_back("eventTime is missing or not ISO-like");
  }
  if (!uuid_shaped(run_id)) {
    reasons.push_back("run.runId is missing or not UUID-shaped");
  }
  if (job_namespace.empty()) {
    reasons.push_back("job.namespace is missing");
  }
  if (job_name.empty()) {
    reasons.push_back("job.name is missing");
  }
  if (producer.empty()) {
    reasons.push_back("producer is missing");
  }
  if (schema_url.find("RunEvent") == std::string::npos) {
    reasons.push_back("schemaURL does not reference RunEvent");
  }
  if (payload.find("\"inputs\"") == std::string::npos) {
    reasons.push_back("inputs section is missing");
  }
  if (payload.find("\"outputs\"") == std::string::npos) {
    reasons.push_back("outputs section is missing");
  }

  const int total_namespaces = count_occurrences(payload, "\"namespace\"");
  const int input_count = payload.find("\"tryops.dataset\"") == std::string::npos ? 0 : 1;
  const int output_count = payload.find("\"tryops.artifact\"") == std::string::npos ? 0 : 1;
  if (total_namespaces < 3) {
    reasons.push_back("event does not contain job plus dataset namespaces");
  }
  if (input_count < 1) {
    reasons.push_back("input dataset namespace was not found");
  }
  if (output_count < 1) {
    reasons.push_back("output artifact namespace was not found");
  }

  const bool passed = reasons.empty();
  emit_report(passed, event_type, run_id, job_namespace, job_name, input_count, output_count, reasons);
  return passed ? 0 : 2;
}
