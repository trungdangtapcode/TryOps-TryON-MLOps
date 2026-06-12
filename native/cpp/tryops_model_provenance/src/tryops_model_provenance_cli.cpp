#include <array>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

namespace {

struct Sha256 {
  std::array<std::uint8_t, 64> data{};
  std::uint32_t datalen = 0;
  std::uint64_t bitlen = 0;
  std::array<std::uint32_t, 8> state{
      0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
      0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U};

  static std::uint32_t rotr(std::uint32_t value, std::uint32_t bits) {
    return (value >> bits) | (value << (32U - bits));
  }

  void transform() {
    static constexpr std::array<std::uint32_t, 64> k{
        0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U, 0x3956c25bU,
        0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U, 0xd807aa98U, 0x12835b01U,
        0x243185beU, 0x550c7dc3U, 0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U,
        0xc19bf174U, 0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
        0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU, 0x983e5152U,
        0xa831c66dU, 0xb00327c8U, 0xbf597fc7U, 0xc6e00bf3U, 0xd5a79147U,
        0x06ca6351U, 0x14292967U, 0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU,
        0x53380d13U, 0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
        0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U, 0xd192e819U,
        0xd6990624U, 0xf40e3585U, 0x106aa070U, 0x19a4c116U, 0x1e376c08U,
        0x2748774cU, 0x34b0bcb5U, 0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU,
        0x682e6ff3U, 0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
        0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U};

    std::array<std::uint32_t, 64> m{};
    for (std::uint32_t i = 0, j = 0; i < 16; ++i, j += 4) {
      m[i] = (static_cast<std::uint32_t>(data[j]) << 24U) |
             (static_cast<std::uint32_t>(data[j + 1]) << 16U) |
             (static_cast<std::uint32_t>(data[j + 2]) << 8U) |
             (static_cast<std::uint32_t>(data[j + 3]));
    }
    for (std::uint32_t i = 16; i < 64; ++i) {
      const std::uint32_t s0 = rotr(m[i - 15], 7U) ^ rotr(m[i - 15], 18U) ^ (m[i - 15] >> 3U);
      const std::uint32_t s1 = rotr(m[i - 2], 17U) ^ rotr(m[i - 2], 19U) ^ (m[i - 2] >> 10U);
      m[i] = m[i - 16] + s0 + m[i - 7] + s1;
    }

    std::uint32_t a = state[0];
    std::uint32_t b = state[1];
    std::uint32_t c = state[2];
    std::uint32_t d = state[3];
    std::uint32_t e = state[4];
    std::uint32_t f = state[5];
    std::uint32_t g = state[6];
    std::uint32_t h = state[7];

    for (std::uint32_t i = 0; i < 64; ++i) {
      const std::uint32_t s1 = rotr(e, 6U) ^ rotr(e, 11U) ^ rotr(e, 25U);
      const std::uint32_t ch = (e & f) ^ ((~e) & g);
      const std::uint32_t temp1 = h + s1 + ch + k[i] + m[i];
      const std::uint32_t s0 = rotr(a, 2U) ^ rotr(a, 13U) ^ rotr(a, 22U);
      const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
      const std::uint32_t temp2 = s0 + maj;

      h = g;
      g = f;
      f = e;
      e = d + temp1;
      d = c;
      c = b;
      b = a;
      a = temp1 + temp2;
    }

    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
    state[5] += f;
    state[6] += g;
    state[7] += h;
  }

  void update(const std::uint8_t* bytes, std::size_t length) {
    for (std::size_t i = 0; i < length; ++i) {
      data[datalen++] = bytes[i];
      if (datalen == 64) {
        transform();
        bitlen += 512;
        datalen = 0;
      }
    }
  }

  std::string final_hex() {
    std::uint32_t i = datalen;
    if (datalen < 56) {
      data[i++] = 0x80U;
      while (i < 56) {
        data[i++] = 0x00U;
      }
    } else {
      data[i++] = 0x80U;
      while (i < 64) {
        data[i++] = 0x00U;
      }
      transform();
      data.fill(0);
    }

    bitlen += static_cast<std::uint64_t>(datalen) * 8U;
    data[63] = static_cast<std::uint8_t>(bitlen);
    data[62] = static_cast<std::uint8_t>(bitlen >> 8U);
    data[61] = static_cast<std::uint8_t>(bitlen >> 16U);
    data[60] = static_cast<std::uint8_t>(bitlen >> 24U);
    data[59] = static_cast<std::uint8_t>(bitlen >> 32U);
    data[58] = static_cast<std::uint8_t>(bitlen >> 40U);
    data[57] = static_cast<std::uint8_t>(bitlen >> 48U);
    data[56] = static_cast<std::uint8_t>(bitlen >> 56U);
    transform();

    std::ostringstream out;
    for (std::uint32_t value : state) {
      out << std::hex << std::setw(8) << std::setfill('0') << value;
    }
    return out.str();
  }
};

std::string sha256_bytes(const std::vector<std::uint8_t>& bytes) {
  Sha256 digest;
  if (!bytes.empty()) {
    digest.update(bytes.data(), bytes.size());
  }
  return digest.final_hex();
}

std::string sha256_string(const std::string& value) {
  const std::vector<std::uint8_t> bytes(value.begin(), value.end());
  return sha256_bytes(bytes);
}

std::string sha256_file(const std::string& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return "";
  }
  Sha256 digest;
  std::array<char, 4096> buffer{};
  while (input.read(buffer.data(), static_cast<std::streamsize>(buffer.size())) || input.gcount() > 0) {
    digest.update(
        reinterpret_cast<const std::uint8_t*>(buffer.data()),
        static_cast<std::size_t>(input.gcount()));
  }
  return digest.final_hex();
}

int base64_value(char ch) {
  if (ch >= 'A' && ch <= 'Z') return ch - 'A';
  if (ch >= 'a' && ch <= 'z') return ch - 'a' + 26;
  if (ch >= '0' && ch <= '9') return ch - '0' + 52;
  if (ch == '+') return 62;
  if (ch == '/') return 63;
  return -1;
}

std::vector<std::uint8_t> base64_decode(const std::string& value) {
  std::vector<std::uint8_t> out;
  int bits = 0;
  int bit_count = 0;
  for (const char ch : value) {
    if (ch == '=') {
      break;
    }
    const int decoded = base64_value(ch);
    if (decoded < 0) {
      continue;
    }
    bits = (bits << 6) | decoded;
    bit_count += 6;
    if (bit_count >= 8) {
      bit_count -= 8;
      out.push_back(static_cast<std::uint8_t>((bits >> bit_count) & 0xff));
    }
  }
  return out;
}

std::string read_file(const std::string& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return "";
  }
  std::ostringstream out;
  out << input.rdbuf();
  return out.str();
}

std::map<std::string, std::string> read_wire() {
  std::map<std::string, std::string> values;
  std::string line;
  while (std::getline(std::cin, line)) {
    const auto separator = line.find('=');
    if (separator == std::string::npos) {
      continue;
    }
    values[line.substr(0, separator)] = line.substr(separator + 1);
  }
  return values;
}

std::string extract_json_string(const std::string& json, const std::string& key) {
  const std::string needle = "\"" + key + "\"";
  const auto key_pos = json.find(needle);
  if (key_pos == std::string::npos) {
    return "";
  }
  const auto colon = json.find(':', key_pos + needle.size());
  if (colon == std::string::npos) {
    return "";
  }
  auto quote = json.find('"', colon + 1);
  if (quote == std::string::npos) {
    return "";
  }
  std::string out;
  bool escaped = false;
  for (std::size_t i = quote + 1; i < json.size(); ++i) {
    const char ch = json[i];
    if (escaped) {
      switch (ch) {
        case 'n': out.push_back('\n'); break;
        case 'r': out.push_back('\r'); break;
        case 't': out.push_back('\t'); break;
        default: out.push_back(ch); break;
      }
      escaped = false;
    } else if (ch == '\\') {
      escaped = true;
    } else if (ch == '"') {
      return out;
    } else {
      out.push_back(ch);
    }
  }
  return "";
}

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    switch (ch) {
      case '\\': out << "\\\\"; break;
      case '"': out << "\\\""; break;
      case '\n': out << "\\n"; break;
      case '\r': out << "\\r"; break;
      case '\t': out << "\\t"; break;
      default: out << ch; break;
    }
  }
  return out.str();
}

void print_report(
    bool passed,
    const std::vector<std::string>& errors,
    const std::map<std::string, std::string>& checks) {
  std::cout << "{";
  std::cout << "\"schema_version\":\"tryops.native_model_provenance.v1\",";
  std::cout << "\"available\":true,";
  std::cout << "\"source\":\"native_cpp_cli\",";
  std::cout << "\"passed\":" << (passed ? "true" : "false") << ",";
  std::cout << "\"errors\":[";
  for (std::size_t i = 0; i < errors.size(); ++i) {
    if (i != 0) std::cout << ",";
    std::cout << "\"" << json_escape(errors[i]) << "\"";
  }
  std::cout << "],\"checks\":{";
  std::size_t index = 0;
  for (const auto& [key, value] : checks) {
    if (index++ != 0) std::cout << ",";
    std::cout << "\"" << json_escape(key) << "\":\"" << json_escape(value) << "\"";
  }
  std::cout << "}}";
  std::cout << "\n";
}

}  // namespace

int main() {
  const auto wire = read_wire();
  const std::string artifact_path = wire.count("artifact_path") ? wire.at("artifact_path") : "";
  const std::string bundle_path = wire.count("bundle_path") ? wire.at("bundle_path") : "";
  const std::string expected_signer =
      wire.count("expected_signer_identity") ? wire.at("expected_signer_identity") : "";
  const std::string expected_predicate =
      wire.count("expected_predicate_type") ? wire.at("expected_predicate_type") : "";

  std::vector<std::string> errors;
  if (artifact_path.empty()) errors.push_back("artifact_path is required");
  if (bundle_path.empty()) errors.push_back("bundle_path is required");

  const std::string bundle = read_file(bundle_path);
  if (bundle.empty()) errors.push_back("signature bundle could not be read");

  const std::string payload_b64 = extract_json_string(bundle, "payload_b64");
  const std::string payload_sha256 = extract_json_string(bundle, "payload_sha256");
  const std::string subject_sha256 = extract_json_string(bundle, "subject_sha256");
  const std::string predicate_type = extract_json_string(bundle, "predicate_type");
  const std::string key_id = extract_json_string(bundle, "key_id");
  const std::string signer_identity = extract_json_string(bundle, "signer_identity");
  const std::string signature_value = extract_json_string(bundle, "value");

  const auto payload_bytes = base64_decode(payload_b64);
  const std::string computed_payload_sha = sha256_bytes(payload_bytes);
  const std::string artifact_sha = sha256_file(artifact_path);
  const std::string expected_signature = sha256_string(key_id + "\n" + payload_b64);

  if (artifact_sha.empty()) errors.push_back("artifact could not be read");
  if (artifact_sha != subject_sha256) errors.push_back("artifact sha256 does not match signed subject");
  if (computed_payload_sha != payload_sha256) errors.push_back("payload sha256 does not match bundle");
  if (signature_value != expected_signature) errors.push_back("local signature digest does not match payload");
  if (!expected_predicate.empty() && predicate_type != expected_predicate) {
    errors.push_back("predicate type does not match expected value");
  }
  if (!expected_signer.empty() && signer_identity != expected_signer) {
    errors.push_back("signer identity mismatch");
  }

  std::map<std::string, std::string> checks{
      {"artifact_sha256", artifact_sha},
      {"subject_sha256", subject_sha256},
      {"payload_sha256", computed_payload_sha},
      {"predicate_type", predicate_type},
      {"signature_algorithm", extract_json_string(bundle, "algorithm")},
      {"signer_identity", signer_identity},
  };
  print_report(errors.empty(), errors, checks);
  return errors.empty() ? 0 : 2;
}
