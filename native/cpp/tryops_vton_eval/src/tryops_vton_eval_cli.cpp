#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

struct Image {
  int width = 0;
  int height = 0;
  std::vector<unsigned char> pixels;
};

struct Box {
  int x = 0;
  int y = 0;
  int width = 0;
  int height = 0;
};

struct Preference {
  std::string winner;
  std::string loser;
  double weight = 1.0;
};

struct SliceQuality {
  std::string skin_tone;
  std::string body_type;
  double quality = 0.0;
};

double clamp01(double value) {
  return std::max(0.0, std::min(1.0, value));
}

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    if (ch == '\\') {
      out << "\\\\";
    } else if (ch == '"') {
      out << "\\\"";
    } else if (ch == '\n') {
      out << "\\n";
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
    bytes.push_back(static_cast<unsigned char>((hex_value(hex[index]) << 4) | hex_value(hex[index + 1])));
  }
  return bytes;
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

std::string get_string(
    const std::unordered_map<std::string, std::string>& values,
    const std::string& key,
    const std::string& fallback = "") {
  const auto found = values.find(key);
  return found == values.end() ? fallback : found->second;
}

int get_int(const std::unordered_map<std::string, std::string>& values, const std::string& key, int fallback = 0) {
  const auto found = values.find(key);
  return found == values.end() ? fallback : std::atoi(found->second.c_str());
}

double get_double(
    const std::unordered_map<std::string, std::string>& values,
    const std::string& key,
    double fallback = 0.0) {
  const auto found = values.find(key);
  return found == values.end() ? fallback : std::atof(found->second.c_str());
}

Image image_from_payload(
    const std::unordered_map<std::string, std::string>& values,
    const std::string& prefix) {
  Image image;
  image.width = get_int(values, prefix + ".width");
  image.height = get_int(values, prefix + ".height");
  image.pixels = decode_hex(values.at(prefix + ".pixels_hex"));
  const std::size_t expected = static_cast<std::size_t>(image.width * image.height * 3);
  if (image.width <= 0 || image.height <= 0 || image.pixels.size() != expected) {
    throw std::runtime_error("invalid image payload for " + prefix);
  }
  return image;
}

Box box_from_payload(const std::unordered_map<std::string, std::string>& values, const std::string& prefix) {
  Box box;
  box.x = get_int(values, prefix + ".x");
  box.y = get_int(values, prefix + ".y");
  box.width = get_int(values, prefix + ".width");
  box.height = get_int(values, prefix + ".height");
  return box;
}

Box clamp_box(const Image& image, Box box) {
  box.x = std::max(0, std::min(image.width - 1, box.x));
  box.y = std::max(0, std::min(image.height - 1, box.y));
  box.width = std::max(1, std::min(image.width - box.x, box.width));
  box.height = std::max(1, std::min(image.height - box.y, box.height));
  return box;
}

std::size_t pixel_index(const Image& image, int x, int y) {
  x = std::max(0, std::min(image.width - 1, x));
  y = std::max(0, std::min(image.height - 1, y));
  return static_cast<std::size_t>((y * image.width + x) * 3);
}

double luma_at(const Image& image, int x, int y) {
  const std::size_t index = pixel_index(image, x, y);
  return 0.299 * image.pixels[index] + 0.587 * image.pixels[index + 1] + 0.114 * image.pixels[index + 2];
}

double luma_in_box(const Image& image, const Box& box, int x, int y, int target_width, int target_height) {
  const int source_x = box.x + std::min(box.width - 1, (x * box.width) / target_width);
  const int source_y = box.y + std::min(box.height - 1, (y * box.height) / target_height);
  return luma_at(image, source_x, source_y);
}

std::uint64_t dhash_box(const Image& image, const Box& box) {
  std::uint64_t hash = 0;
  int bit = 0;
  for (int y = 0; y < 8; ++y) {
    for (int x = 0; x < 8; ++x) {
      const double left = luma_in_box(image, box, x, y, 9, 8);
      const double right = luma_in_box(image, box, x + 1, y, 9, 8);
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

std::vector<double> region_embedding(const Image& image, Box box) {
  box = clamp_box(image, box);
  std::vector<double> features(16, 0.0);
  const double n = static_cast<double>(box.width * box.height);
  double sum_r = 0.0;
  double sum_g = 0.0;
  double sum_b = 0.0;
  double sum_r2 = 0.0;
  double sum_g2 = 0.0;
  double sum_b2 = 0.0;
  double edge_total = 0.0;

  for (int y = box.y; y < box.y + box.height; ++y) {
    for (int x = box.x; x < box.x + box.width; ++x) {
      const std::size_t index = pixel_index(image, x, y);
      const double r = image.pixels[index];
      const double g = image.pixels[index + 1];
      const double b = image.pixels[index + 2];
      sum_r += r;
      sum_g += g;
      sum_b += b;
      sum_r2 += r * r;
      sum_g2 += g * g;
      sum_b2 += b * b;
      const double luma = 0.299 * r + 0.587 * g + 0.114 * b;
      const int bin = std::max(0, std::min(7, static_cast<int>(luma / 32.0)));
      features[6 + bin] += 1.0;
      edge_total += std::abs(luma_at(image, x + 1, y) - luma_at(image, x - 1, y)) +
                    std::abs(luma_at(image, x, y + 1) - luma_at(image, x, y - 1));
    }
  }

  const double mean_r = sum_r / n;
  const double mean_g = sum_g / n;
  const double mean_b = sum_b / n;
  features[0] = mean_r / 255.0;
  features[1] = mean_g / 255.0;
  features[2] = mean_b / 255.0;
  features[3] = std::sqrt(std::max(0.0, sum_r2 / n - mean_r * mean_r)) / 128.0;
  features[4] = std::sqrt(std::max(0.0, sum_g2 / n - mean_g * mean_g)) / 128.0;
  features[5] = std::sqrt(std::max(0.0, sum_b2 / n - mean_b * mean_b)) / 128.0;
  for (int index = 6; index < 14; ++index) {
    features[index] /= n;
  }
  features[14] = edge_total / (n * 510.0);
  features[15] = static_cast<double>(box.width) / std::max(1, image.width);
  return features;
}

double embedding_distance(const std::vector<double>& left, const std::vector<double>& right) {
  if (left.size() != right.size()) {
    throw std::runtime_error("embedding vectors must have same size");
  }
  double total = 0.0;
  for (std::size_t index = 0; index < left.size(); ++index) {
    const double diff = left[index] - right[index];
    total += diff * diff;
  }
  return std::sqrt(total / static_cast<double>(left.size()));
}

double patch_mse_resized(const Image& source, const Image& target, Box target_box) {
  target_box = clamp_box(target, target_box);
  double total = 0.0;
  int count = 0;
  for (int y = 0; y < target_box.height; ++y) {
    const int source_y = std::min(source.height - 1, (y * source.height) / target_box.height);
    const int target_y = target_box.y + y;
    for (int x = 0; x < target_box.width; ++x) {
      const int source_x = std::min(source.width - 1, (x * source.width) / target_box.width);
      const int target_x = target_box.x + x;
      const std::size_t source_index = pixel_index(source, source_x, source_y);
      const std::size_t target_index = pixel_index(target, target_x, target_y);
      for (int channel = 0; channel < 3; ++channel) {
        const double diff =
            static_cast<double>(source.pixels[source_index + channel]) -
            static_cast<double>(target.pixels[target_index + channel]);
        total += diff * diff;
        ++count;
      }
    }
  }
  return total / static_cast<double>(count);
}

double patch_edge_delta_resized(const Image& source, const Image& target, Box target_box) {
  target_box = clamp_box(target, target_box);
  if (target_box.width < 3 || target_box.height < 3) {
    return 0.0;
  }
  double total = 0.0;
  int count = 0;
  const Box source_box{0, 0, source.width, source.height};
  for (int y = 1; y < target_box.height - 1; ++y) {
    for (int x = 1; x < target_box.width - 1; ++x) {
      const double source_gradient =
          std::abs(luma_in_box(source, source_box, x + 1, y, target_box.width, target_box.height) -
                   luma_in_box(source, source_box, x - 1, y, target_box.width, target_box.height)) +
          std::abs(luma_in_box(source, source_box, x, y + 1, target_box.width, target_box.height) -
                   luma_in_box(source, source_box, x, y - 1, target_box.width, target_box.height));
      const double target_gradient =
          std::abs(luma_at(target, target_box.x + x + 1, target_box.y + y) -
                   luma_at(target, target_box.x + x - 1, target_box.y + y)) +
          std::abs(luma_at(target, target_box.x + x, target_box.y + y + 1) -
                   luma_at(target, target_box.x + x, target_box.y + y - 1));
      total += std::abs(source_gradient - target_gradient);
      ++count;
    }
  }
  return total / (static_cast<double>(count) * 510.0);
}

std::vector<Preference> parse_preferences(const std::unordered_map<std::string, std::string>& values) {
  std::vector<Preference> preferences;
  const int count = get_int(values, "preference.count", 0);
  for (int index = 0; index < count; ++index) {
    const std::string prefix = "preference." + std::to_string(index) + ".";
    Preference preference;
    preference.winner = get_string(values, prefix + "winner");
    preference.loser = get_string(values, prefix + "loser");
    preference.weight = std::max(0.0, get_double(values, prefix + "weight", 1.0));
    if (!preference.winner.empty() && !preference.loser.empty() && preference.winner != preference.loser) {
      preferences.push_back(preference);
    }
  }
  return preferences;
}

std::vector<SliceQuality> parse_slices(const std::unordered_map<std::string, std::string>& values) {
  std::vector<SliceQuality> slices;
  const int count = get_int(values, "slice.count", 0);
  for (int index = 0; index < count; ++index) {
    const std::string prefix = "slice." + std::to_string(index) + ".";
    SliceQuality slice;
    slice.skin_tone = get_string(values, prefix + "skin_tone");
    slice.body_type = get_string(values, prefix + "body_type");
    slice.quality = get_double(values, prefix + "quality", 0.0);
    if (!slice.skin_tone.empty() && !slice.body_type.empty()) {
      slices.push_back(slice);
    }
  }
  return slices;
}

std::map<std::string, double> average_by_key(
    const std::vector<SliceQuality>& slices,
    const std::string& key_name) {
  std::map<std::string, std::pair<double, int>> accumulator;
  for (const auto& slice : slices) {
    const std::string key = key_name == "skin_tone" ? slice.skin_tone : slice.body_type;
    accumulator[key].first += slice.quality;
    accumulator[key].second += 1;
  }
  std::map<std::string, double> averages;
  for (const auto& [key, total_count] : accumulator) {
    averages[key] = total_count.first / static_cast<double>(std::max(1, total_count.second));
  }
  return averages;
}

double max_gap(const std::map<std::string, double>& values) {
  if (values.empty()) {
    return 0.0;
  }
  double min_value = values.begin()->second;
  double max_value = values.begin()->second;
  for (const auto& [_, value] : values) {
    min_value = std::min(min_value, value);
    max_value = std::max(max_value, value);
  }
  return max_value - min_value;
}

std::vector<std::pair<std::string, double>> fit_bradley_terry(const std::vector<Preference>& preferences) {
  std::map<std::string, int> index_by_name;
  for (const auto& preference : preferences) {
    if (!index_by_name.count(preference.winner)) {
      index_by_name[preference.winner] = static_cast<int>(index_by_name.size());
    }
    if (!index_by_name.count(preference.loser)) {
      index_by_name[preference.loser] = static_cast<int>(index_by_name.size());
    }
  }
  const int n = static_cast<int>(index_by_name.size());
  std::vector<std::string> names(n);
  for (const auto& [name, index] : index_by_name) {
    names[index] = name;
  }
  std::vector<std::vector<double>> comparisons(n, std::vector<double>(n, 0.0));
  std::vector<double> wins(n, 0.0);
  for (const auto& preference : preferences) {
    const int winner = index_by_name[preference.winner];
    const int loser = index_by_name[preference.loser];
    comparisons[winner][loser] += preference.weight;
    comparisons[loser][winner] += preference.weight;
    wins[winner] += preference.weight;
  }

  std::vector<double> strength(n, 1.0);
  for (int iter = 0; iter < 200; ++iter) {
    std::vector<double> next(n, 1.0);
    for (int i = 0; i < n; ++i) {
      double denom = 0.0;
      for (int j = 0; j < n; ++j) {
        if (i == j || comparisons[i][j] <= 0.0) {
          continue;
        }
        denom += comparisons[i][j] / std::max(1e-9, strength[i] + strength[j]);
      }
      next[i] = (wins[i] + 0.5) / std::max(1e-9, denom + 0.5);
    }
    const double mean_strength =
        std::accumulate(next.begin(), next.end(), 0.0) / static_cast<double>(std::max(1, n));
    for (double& value : next) {
      value /= std::max(1e-9, mean_strength);
    }
    strength = next;
  }

  std::vector<std::pair<std::string, double>> ranking;
  for (int i = 0; i < n; ++i) {
    ranking.push_back({names[i], strength[i]});
  }
  std::sort(ranking.begin(), ranking.end(), [](const auto& left, const auto& right) {
    if (std::abs(left.second - right.second) > 1e-9) {
      return left.second > right.second;
    }
    return left.first < right.first;
  });
  return ranking;
}

void write_named_scores(const std::map<std::string, double>& scores) {
  std::cout << "{";
  bool first = true;
  for (const auto& [name, score] : scores) {
    if (!first) {
      std::cout << ",";
    }
    std::cout << "\"" << json_escape(name) << "\":" << score;
    first = false;
  }
  std::cout << "}";
}

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    const Image person = image_from_payload(payload, "person");
    const Image garment = image_from_payload(payload, "garment");
    const Image output = image_from_payload(payload, "output");
    if (person.width != output.width || person.height != output.height) {
      throw std::runtime_error("person and output images must have the same dimensions");
    }
    const Box overlay = clamp_box(output, box_from_payload(payload, "overlay"));
    const Box face_box{
        std::max(0, person.width / 4),
        0,
        std::max(1, person.width / 2),
        std::max(1, static_cast<int>(std::round(person.height * 0.24))),
    };

    const double identity_distance = embedding_distance(region_embedding(person, face_box), region_embedding(output, face_box));
    const double identity_score = clamp01(1.0 - identity_distance);

    const double garment_mse = patch_mse_resized(garment, output, overlay);
    const double garment_psnr = garment_mse == 0.0 ? 999.0 : 20.0 * std::log10(255.0 / std::sqrt(garment_mse));
    const double garment_edge = patch_edge_delta_resized(garment, output, overlay);
    const double garment_dhash =
        1.0 - static_cast<double>(popcount64(dhash_box(garment, Box{0, 0, garment.width, garment.height}) ^
                                             dhash_box(output, overlay))) /
                  64.0;
    const double garment_score = clamp01(
        0.45 * garment_dhash + 0.35 * (1.0 - std::min(1.0, garment_mse / 65025.0)) + 0.20 * (1.0 - garment_edge));

    const double expected_x = person.width * 0.5;
    const double expected_y = person.height * 0.535;
    const double overlay_x = overlay.x + overlay.width * 0.5;
    const double overlay_y = overlay.y + overlay.height * 0.5;
    const double pose_distance =
        std::sqrt((overlay_x - expected_x) * (overlay_x - expected_x) +
                  (overlay_y - expected_y) * (overlay_y - expected_y)) /
        std::sqrt(static_cast<double>(person.width * person.width + person.height * person.height));
    const double pose_score = clamp01(1.0 - 2.0 * pose_distance);

    const auto slices = parse_slices(payload);
    const auto skin_scores = average_by_key(slices, "skin_tone");
    const auto body_scores = average_by_key(slices, "body_type");
    const double skin_gap = max_gap(skin_scores);
    const double body_gap = max_gap(body_scores);
    const double fairness_threshold = get_double(payload, "fairness.max_gap", 0.08);
    const bool fairness_passed = !slices.empty() && skin_gap <= fairness_threshold && body_gap <= fairness_threshold;

    const auto preferences = parse_preferences(payload);
    const auto ranking = fit_bradley_terry(preferences);

    const double quality_index = 0.35 * identity_score + 0.35 * garment_score + 0.20 * pose_score +
                                 0.10 * (fairness_passed ? 1.0 : std::max(0.0, 1.0 - std::max(skin_gap, body_gap)));

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "{";
    std::cout << "\"schema_version\":\"tryops.native_vton_eval.v1\",";
    std::cout << "\"identity\":{\"method\":\"native_face_region_embedding_proxy\",";
    std::cout << "\"embedding_distance\":" << identity_distance << ",\"score\":" << identity_score << ",";
    std::cout << "\"face_region\":{\"x\":" << face_box.x << ",\"y\":" << face_box.y << ",\"width\":"
              << face_box.width << ",\"height\":" << face_box.height << "}},";
    std::cout << "\"garment_fidelity\":{\"method\":\"native_masked_patch_fidelity_proxy\",";
    std::cout << "\"mse\":" << garment_mse << ",\"psnr\":" << garment_psnr << ",\"dhash_similarity\":"
              << garment_dhash << ",\"edge_delta\":" << garment_edge << ",\"score\":" << garment_score << ",";
    std::cout << "\"overlay\":{\"x\":" << overlay.x << ",\"y\":" << overlay.y << ",\"width\":" << overlay.width
              << ",\"height\":" << overlay.height << "}},";
    std::cout << "\"pose_consistency\":{\"method\":\"native_torso_alignment_proxy\",";
    std::cout << "\"normalized_distance\":" << pose_distance << ",\"score\":" << pose_score << "},";
    std::cout << "\"fairness\":{\"available\":" << (slices.empty() ? "false" : "true") << ",";
    std::cout << "\"record_count\":" << slices.size() << ",\"max_gap_threshold\":" << fairness_threshold << ",";
    std::cout << "\"skin_tone_gap\":" << skin_gap << ",\"body_type_gap\":" << body_gap << ",";
    std::cout << "\"passed\":" << (fairness_passed ? "true" : "false") << ",";
    std::cout << "\"skin_tone_scores\":";
    write_named_scores(skin_scores);
    std::cout << ",\"body_type_scores\":";
    write_named_scores(body_scores);
    std::cout << "},";
    std::cout << "\"preference_ranking\":{\"available\":" << (ranking.empty() ? "false" : "true")
              << ",\"method\":\"bradley_terry_mm\",";
    std::cout << "\"comparison_count\":" << preferences.size() << ",\"ranking\":[";
    for (std::size_t index = 0; index < ranking.size(); ++index) {
      if (index != 0) {
        std::cout << ",";
      }
      std::cout << "{\"rank\":" << (index + 1) << ",\"item\":\"" << json_escape(ranking[index].first)
                << "\",\"strength\":" << ranking[index].second << "}";
    }
    std::cout << "]},";
    std::cout << "\"quality_index\":" << quality_index << ",";
    std::cout << "\"passed\":" << ((quality_index >= 0.72 && fairness_passed) ? "true" : "false");
    std::cout << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
