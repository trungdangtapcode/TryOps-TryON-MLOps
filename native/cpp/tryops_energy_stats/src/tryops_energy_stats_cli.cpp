// tryops_energy_stats: native energy / carbon aggregation and carbon-aware gate.
//
// Green-MLOps hot path in compiled C++ rather than Python, matching the platform
// decision that Python is the ML lab layer while native code carries the
// production boundary. Given a GPU power trace (watts) and a run duration, it
// computes energy, CO2e, Software Carbon Intensity (SCI) per 1k tokens, and a
// carbon-aware promotion verdict.
//
// Protocol (matching the other tryops native CLIs): read `key=value` lines from
// stdin, emit one JSON object on stdout, emit `{"error":...}` on stderr with a
// non-zero exit code on failure.
//
// Input keys:
//   samples.power_w=17.2,150.3,148.9     (comma-separated watts, >=1 sample)
//   duration_s=2.5                       (wall-clock seconds, > 0)
//   tokens=300                           (optional functional unit; default 0)
//   grid_intensity_g_per_kwh=475         (optional; default 475 world avg)
//   slo.energy_wh_per_1k_tokens_max=5.0  (optional carbon-aware gate)

#include <algorithm>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    if (ch == '\\' || ch == '"') {
      out << '\\' << ch;
    } else {
      out << ch;
    }
  }
  return out.str();
}

std::vector<double> parse_doubles(const std::string& csv) {
  std::vector<double> values;
  std::stringstream stream(csv);
  std::string token;
  while (std::getline(stream, token, ',')) {
    const auto begin = token.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
      continue;
    }
    const auto end = token.find_last_not_of(" \t\r\n");
    values.push_back(std::stod(token.substr(begin, end - begin + 1)));
  }
  return values;
}

double mean(const std::vector<double>& values) {
  double total = 0.0;
  for (const double v : values) {
    total += v;
  }
  return total / static_cast<double>(values.size());
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

}  // namespace

int main() {
  try {
    const auto payload = read_payload();
    if (payload.find("samples.power_w") == payload.end()) {
      throw std::runtime_error("missing required key samples.power_w");
    }
    if (payload.find("duration_s") == payload.end()) {
      throw std::runtime_error("missing required key duration_s");
    }
    const std::vector<double> power = parse_doubles(payload.at("samples.power_w"));
    if (power.empty()) {
      throw std::runtime_error("samples.power_w produced no values");
    }
    const double duration_s = std::stod(payload.at("duration_s"));
    if (duration_s <= 0.0) {
      throw std::runtime_error("duration_s must be > 0");
    }

    double tokens = 0.0;
    const auto tokens_it = payload.find("tokens");
    if (tokens_it != payload.end()) {
      tokens = std::stod(tokens_it->second);
    }
    double grid = 475.0;  // gCO2e/kWh — documented world-average default
    const auto grid_it = payload.find("grid_intensity_g_per_kwh");
    if (grid_it != payload.end()) {
      grid = std::stod(grid_it->second);
    }

    const double mean_w = mean(power);
    const double peak_w = *std::max_element(power.begin(), power.end());
    const double min_w = *std::min_element(power.begin(), power.end());
    // Uniform-sampling energy estimate: mean power over the wall-clock window.
    const double energy_j = mean_w * duration_s;
    const double energy_wh = energy_j / 3600.0;
    const double energy_kwh = energy_wh / 1000.0;
    const double co2eq_g = energy_kwh * grid;

    double energy_wh_per_1k = 0.0;
    double sci_g_per_1k = 0.0;
    double tokens_per_joule = 0.0;
    if (tokens > 0.0) {
      energy_wh_per_1k = energy_wh / tokens * 1000.0;
      sci_g_per_1k = co2eq_g / tokens * 1000.0;
      tokens_per_joule = tokens / energy_j;
    }
    const double energy_delay_product = energy_j * duration_s;  // EDP (J·s)

    bool gate_evaluated = false;
    bool gate_pass = true;
    double gate_max = 0.0;
    const auto gate_it = payload.find("slo.energy_wh_per_1k_tokens_max");
    if (gate_it != payload.end() && tokens > 0.0) {
      gate_evaluated = true;
      gate_max = std::stod(gate_it->second);
      gate_pass = energy_wh_per_1k <= gate_max;
    }

    std::cout.precision(6);
    std::cout << std::fixed;
    std::cout << "{";
    std::cout << "\"schema_version\":\"tryops.native_energy_stats.v1\",";
    std::cout << "\"power_w\":{\"mean\":" << mean_w << ",\"peak\":" << peak_w
              << ",\"min\":" << min_w << ",\"samples\":" << power.size() << "},";
    std::cout << "\"duration_s\":" << duration_s << ",";
    std::cout << "\"tokens\":" << tokens << ",";
    std::cout << "\"grid_intensity_g_per_kwh\":" << grid << ",";
    std::cout << "\"energy_j\":" << energy_j << ",";
    std::cout << "\"energy_wh\":" << energy_wh << ",";
    std::cout << "\"energy_kwh\":" << energy_kwh << ",";
    std::cout << "\"co2eq_g\":" << co2eq_g << ",";
    std::cout << "\"energy_wh_per_1k_tokens\":" << energy_wh_per_1k << ",";
    std::cout << "\"sci_g_per_1k_tokens\":" << sci_g_per_1k << ",";
    std::cout << "\"tokens_per_joule\":" << tokens_per_joule << ",";
    std::cout << "\"energy_delay_product_js\":" << energy_delay_product << ",";
    std::cout << "\"gate\":{";
    std::cout << "\"evaluated\":" << (gate_evaluated ? "true" : "false") << ",";
    if (gate_it != payload.end()) {
      std::cout << "\"energy_wh_per_1k_tokens_max\":" << gate_max << ",";
    }
    std::cout << "\"pass\":" << (gate_pass ? "true" : "false") << ",";
    std::cout << "\"verdict\":\"" << (gate_pass ? "pass" : "fail") << "\"";
    std::cout << "}";
    std::cout << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"error\":\"" << json_escape(error.what()) << "\"}\n";
    return 2;
  }
}
