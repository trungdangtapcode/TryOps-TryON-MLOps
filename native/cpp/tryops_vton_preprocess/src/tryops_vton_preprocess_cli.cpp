#include <algorithm>
#include <cmath>
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

struct BBox {
  bool available = false;
  int x = 0;
  int y = 0;
  int width = 0;
  int height = 0;
};

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
    bytes.push_back(static_cast<unsigned char>((hex_value(hex[index]) << 4) | hex_value(hex[index + 1])));
  }
  return bytes;
}

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

Image image_from_payload(const std::unordered_map<std::string, std::string>& values) {
  Image image;
  image.width = std::atoi(values.at("width").c_str());
  image.height = std::atoi(values.at("height").c_str());
  image.pixels = decode_hex(values.at("pixels_hex"));
  const std::size_t expected = static_cast<std::size_t>(image.width * image.height * 3);
  if (image.width <= 0 || image.height <= 0 || image.pixels.size() != expected) {
    throw std::runtime_error("invalid image payload");
  }
  return image;
}

std::vector<int> background_rgb(const Image& image) {
  const std::vector<std::pair<int, int>> points = {
      {0, 0}, {image.width - 1, 0}, {0, image.height - 1}, {image.width - 1, image.height - 1}};
  std::vector<int> rgb = {0, 0, 0};
  for (const auto& point : points) {
    const std::size_t index = static_cast<std::size_t>((point.second * image.width + point.first) * 3);
    rgb[0] += image.pixels[index];
    rgb[1] += image.pixels[index + 1];
    rgb[2] += image.pixels[index + 2];
  }
  for (int& value : rgb) {
    value = static_cast<int>(std::round(value / 4.0));
  }
  return rgb;
}

double color_distance(const Image& image, int pixel_index, const std::vector<int>& background) {
  const std::size_t index = static_cast<std::size_t>(pixel_index * 3);
  double total = 0.0;
  for (int channel = 0; channel < 3; ++channel) {
    const double diff = static_cast<double>(image.pixels[index + channel]) - static_cast<double>(background[channel]);
    total += diff * diff;
  }
  return std::sqrt(total);
}

std::vector<bool> foreground_mask(const Image& image, const std::string& role, double threshold) {
  const auto background = background_rgb(image);
  std::vector<bool> mask;
  mask.reserve(static_cast<std::size_t>(image.width * image.height));
  int foreground_count = 0;
  for (int index = 0; index < image.width * image.height; ++index) {
    const bool foreground = color_distance(image, index, background) >= threshold;
    mask.push_back(foreground);
    if (foreground) {
      ++foreground_count;
    }
  }
  const double coverage = static_cast<double>(foreground_count) / static_cast<double>(image.width * image.height);
  if (role == "garment" && (coverage < 0.05 || coverage > 0.98)) {
    return std::vector<bool>(static_cast<std::size_t>(image.width * image.height), true);
  }
  return mask;
}

BBox bbox_from_mask(const std::vector<bool>& mask, int width, int height) {
  BBox bbox;
  int min_x = width;
  int min_y = height;
  int max_x = -1;
  int max_y = -1;
  for (int index = 0; index < width * height; ++index) {
    if (!mask[static_cast<std::size_t>(index)]) {
      continue;
    }
    const int x = index % width;
    const int y = index / width;
    min_x = std::min(min_x, x);
    min_y = std::min(min_y, y);
    max_x = std::max(max_x, x);
    max_y = std::max(max_y, y);
  }
  if (max_x >= min_x && max_y >= min_y) {
    bbox.available = true;
    bbox.x = min_x;
    bbox.y = min_y;
    bbox.width = max_x - min_x + 1;
    bbox.height = max_y - min_y + 1;
  }
  return bbox;
}

double coverage(const std::vector<bool>& mask) {
  int count = 0;
  for (const bool value : mask) {
    if (value) {
      ++count;
    }
  }
  return static_cast<double>(count) / static_cast<double>(mask.size());
}

void print_bbox(const BBox& bbox) {
  if (!bbox.available) {
    std::cout << "null";
    return;
  }
  std::cout << "{\"x\":" << bbox.x << ",\"y\":" << bbox.y << ",\"width\":" << bbox.width
            << ",\"height\":" << bbox.height << "}";
}

void print_pose(const BBox& bbox, int image_width, int image_height) {
  if (!bbox.available) {
    std::cout << "{\"available\":false,\"method\":\"heuristic_foreground_bbox\",\"confidence\":0.0,\"keypoints\":{}}";
    return;
  }
  const double x = bbox.x;
  const double y = bbox.y;
  const double width = bbox.width;
  const double height = bbox.height;
  const double center_x = x + width / 2.0;
  const double confidence =
      std::min(0.95, std::max(0.1, (width * height) / static_cast<double>(image_width * image_height)));
  std::cout << "{\"available\":true,\"method\":\"heuristic_foreground_bbox\",\"confidence\":" << confidence;
  std::cout << ",\"keypoints\":{";
  std::cout << "\"neck\":{\"x\":" << static_cast<int>(std::round(center_x)) << ",\"y\":"
            << static_cast<int>(std::round(y + height * 0.18)) << "},";
  std::cout << "\"left_shoulder\":{\"x\":" << static_cast<int>(std::round(x + width * 0.24)) << ",\"y\":"
            << static_cast<int>(std::round(y + height * 0.28)) << "},";
  std::cout << "\"right_shoulder\":{\"x\":" << static_cast<int>(std::round(x + width * 0.76)) << ",\"y\":"
            << static_cast<int>(std::round(y + height * 0.28)) << "},";
  std::cout << "\"torso_center\":{\"x\":" << static_cast<int>(std::round(center_x)) << ",\"y\":"
            << static_cast<int>(std::round(y + height * 0.50)) << "},";
  std::cout << "\"left_hip\":{\"x\":" << static_cast<int>(std::round(x + width * 0.32)) << ",\"y\":"
            << static_cast<int>(std::round(y + height * 0.75)) << "},";
  std::cout << "\"right_hip\":{\"x\":" << static_cast<int>(std::round(x + width * 0.68)) << ",\"y\":"
            << static_cast<int>(std::round(y + height * 0.75)) << "}";
  std::cout << "}}";
}

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    const std::string role = payload.at("role");
    if (role != "person" && role != "garment") {
      throw std::runtime_error("role must be person or garment");
    }
    const Image image = image_from_payload(payload);
    const auto mask = foreground_mask(image, role, 32.0);
    const BBox bbox = bbox_from_mask(mask, image.width, image.height);
    std::cout << "{\"schema_version\":\"tryops.native_vton_preprocess.v1\",";
    std::cout << "\"role\":\"" << json_escape(role) << "\",";
    std::cout << "\"coverage\":" << coverage(mask) << ",";
    std::cout << "\"bbox\":";
    print_bbox(bbox);
    std::cout << ",\"pose_hints\":";
    print_pose(role == "person" ? bbox : BBox{}, image.width, image.height);
    std::cout << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
