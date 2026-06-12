// Reads raw text on stdin, redacts PII/secrets, prints a JSON report on stdout.
// With --emit-redacted the masked text is included in the JSON (escaped);
// otherwise only counts + fingerprints are emitted (safe for logs).
// Exit code: 0 if nothing sensitive was found, 2 if redactions occurred.
#include "tryops_redaction.hpp"

#include <iostream>
#include <sstream>
#include <string>

namespace {

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (unsigned char ch : value) {
    switch (ch) {
      case '\\': out << "\\\\"; break;
      case '"': out << "\\\""; break;
      case '\n': out << "\\n"; break;
      case '\r': out << "\\r"; break;
      case '\t': out << "\\t"; break;
      default:
        if (ch < 0x20) {
          out << "\\u" << std::hex << std::uppercase;
          out.width(4);
          out.fill('0');
          out << static_cast<int>(ch);
          out << std::dec << std::nouppercase;
        } else {
          out << ch;
        }
    }
  }
  return out.str();
}

}  // namespace

int main(int argc, char** argv) {
  bool emit_redacted = false;
  for (int i = 1; i < argc; ++i) {
    if (std::string(argv[i]) == "--emit-redacted") {
      emit_redacted = true;
    }
  }

  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  const tryops::RedactionResult result = tryops::redact(buffer.str());

  std::cout << "{";
  std::cout << "\"total\":" << result.total << ",";
  std::cout << "\"input_fingerprint\":\"" << std::hex << result.input_fingerprint
            << "\",";
  std::cout << "\"output_fingerprint\":\"" << result.output_fingerprint << "\""
            << std::dec << ",";
  std::cout << "\"counts\":{";
  bool first = true;
  for (const auto& kv : result.counts) {
    if (!first) {
      std::cout << ",";
    }
    first = false;
    std::cout << "\"" << kv.first << "\":" << kv.second;
  }
  std::cout << "}";
  if (emit_redacted) {
    std::cout << ",\"redacted\":\"" << json_escape(result.redacted) << "\"";
  }
  std::cout << "}\n";

  return result.total > 0 ? 2 : 0;
}
