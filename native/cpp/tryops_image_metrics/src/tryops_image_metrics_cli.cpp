#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

struct Image {
  int width = 0;
  int height = 0;
  std::vector<unsigned char> pixels;
};

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    if (ch == '\\') {
      out << "\\\\";
    } else if (ch == '"') {
      out << "\\\"";
    } else {
      out << ch;
    }
  }
  return out.str();
}

int hex_value(char ch) {
  if (ch >= '0' && ch <= '9') {
    return ch - '0';
  }
  if (ch >= 'a' && ch <= 'f') {
    return 10 + ch - 'a';
  }
  if (ch >= 'A' && ch <= 'F') {
    return 10 + ch - 'A';
  }
  throw std::runtime_error("invalid hex byte");
}

std::vector<unsigned char> decode_hex(const std::string& hex) {
  if (hex.size() % 2 != 0) {
    throw std::runtime_error("hex payload length must be even");
  }
  std::vector<unsigned char> bytes;
  bytes.reserve(hex.size() / 2);
  for (std::size_t index = 0; index < hex.size(); index += 2) {
    const int high = hex_value(hex[index]);
    const int low = hex_value(hex[index + 1]);
    bytes.push_back(static_cast<unsigned char>((high << 4) | low));
  }
  return bytes;
}

double luma_at(const Image& image, int x, int y) {
  x = std::max(0, std::min(image.width - 1, x));
  y = std::max(0, std::min(image.height - 1, y));
  const std::size_t index = static_cast<std::size_t>((y * image.width + x) * 3);
  const unsigned char red = image.pixels[index];
  const unsigned char green = image.pixels[index + 1];
  const unsigned char blue = image.pixels[index + 2];
  return 0.299 * red + 0.587 * green + 0.114 * blue;
}

double resized_luma_at(const Image& image, int x, int y, int target_width, int target_height) {
  const int source_x = std::min(image.width - 1, (x * image.width) / target_width);
  const int source_y = std::min(image.height - 1, (y * image.height) / target_height);
  return luma_at(image, source_x, source_y);
}

std::uint64_t dhash64(const Image& image) {
  std::uint64_t hash = 0;
  int bit = 0;
  for (int y = 0; y < 8; ++y) {
    for (int x = 0; x < 8; ++x) {
      const double left = resized_luma_at(image, x, y, 9, 8);
      const double right = resized_luma_at(image, x + 1, y, 9, 8);
      if (left > right) {
        hash |= (std::uint64_t{1} << bit);
      }
      ++bit;
    }
  }
  return hash;
}

int popcount64(std::uint64_t value) {
  int count = 0;
  while (value != 0) {
    value &= value - 1;
    ++count;
  }
  return count;
}

double mse_same_size(const Image& left, const Image& right) {
  if (left.width != right.width || left.height != right.height) {
    throw std::runtime_error("native CLI expects same-sized images");
  }
  double total = 0.0;
  for (std::size_t index = 0; index < left.pixels.size(); ++index) {
    const double diff = static_cast<double>(left.pixels[index]) - static_cast<double>(right.pixels[index]);
    total += diff * diff;
  }
  return total / static_cast<double>(left.pixels.size());
}

double edge_delta(const Image& left, const Image& right) {
  if (left.width != right.width || left.height != right.height) {
    throw std::runtime_error("native CLI expects same-sized images");
  }
  if (left.width < 3 || left.height < 3) {
    return 0.0;
  }
  double total = 0.0;
  int count = 0;
  for (int y = 1; y < left.height - 1; ++y) {
    for (int x = 1; x < left.width - 1; ++x) {
      const double left_gradient =
          std::abs(luma_at(left, x + 1, y) - luma_at(left, x - 1, y)) +
          std::abs(luma_at(left, x, y + 1) - luma_at(left, x, y - 1));
      const double right_gradient =
          std::abs(luma_at(right, x + 1, y) - luma_at(right, x - 1, y)) +
          std::abs(luma_at(right, x, y + 1) - luma_at(right, x, y - 1));
      total += std::abs(left_gradient - right_gradient);
      ++count;
    }
  }
  return total / (static_cast<double>(count) * 510.0);
}

std::unordered_map<std::string, std::string> read_payload() {
  std::unordered_map<std::string, std::string> values;
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

Image image_from_payload(
    const std::unordered_map<std::string, std::string>& values,
    const std::string& prefix) {
  Image image;
  image.width = std::atoi(values.at(prefix + ".width").c_str());
  image.height = std::atoi(values.at(prefix + ".height").c_str());
  image.pixels = decode_hex(values.at(prefix + ".pixels_hex"));
  const std::size_t expected = static_cast<std::size_t>(image.width * image.height * 3);
  if (image.width <= 0 || image.height <= 0 || image.pixels.size() != expected) {
    throw std::runtime_error("invalid image payload for " + prefix);
  }
  return image;
}

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    const Image reference = image_from_payload(payload, "reference");
    const Image candidate = image_from_payload(payload, "candidate");
    const double mse = mse_same_size(reference, candidate);
    const double psnr = mse == 0.0 ? 999.0 : 20.0 * std::log10(255.0 / std::sqrt(mse));
    const int dhash_distance = popcount64(dhash64(reference) ^ dhash64(candidate));
    const double dhash_similarity = 1.0 - (static_cast<double>(dhash_distance) / 64.0);
    const double edge = edge_delta(reference, candidate);

    std::cout << "{";
    std::cout << "\"schema_version\":\"tryops.native_image_metrics.v1\",";
    std::cout << "\"mse\":" << mse << ",";
    std::cout << "\"psnr\":" << psnr << ",";
    std::cout << "\"dhash_distance\":" << dhash_distance << ",";
    std::cout << "\"dhash_similarity\":" << dhash_similarity << ",";
    std::cout << "\"edge_delta\":" << edge;
    std::cout << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
