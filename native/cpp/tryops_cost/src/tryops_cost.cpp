#include "tryops_cost.hpp"

#include <cstdlib>
#include <sstream>

namespace tryops {

const ModelPrice& PricingConfig::price_for(const std::string& model) const {
  const auto found = model_prices.find(model);
  if (found != model_prices.end()) {
    return found->second;
  }
  return default_price;
}

void CostBucket::add(const UsageEvent& ev, const PricingConfig& cfg) {
  const ModelPrice& price = cfg.price_for(ev.model);
  const double token_usd = (ev.in_tokens / 1000.0) * price.in_per_1k +
                           (ev.out_tokens / 1000.0) * price.out_per_1k;
  const double gpu_usd = (ev.gpu_seconds / 3600.0) * cfg.gpu_usd_per_hr;
  const double kwh = ev.energy_wh / 1000.0;
  const double energy_usd = kwh * cfg.electricity_usd_per_kwh;
  const double carbon = kwh * cfg.grid_g_per_kwh;

  requests += 1;
  in_tokens += ev.in_tokens;
  out_tokens += ev.out_tokens;
  this->token_usd += token_usd;
  this->gpu_usd += gpu_usd;
  this->energy_usd += energy_usd;
  this->total_usd += token_usd + gpu_usd + energy_usd;
  this->carbon_g += carbon;
}

namespace {

double parse_double(const std::string& v, double fallback) {
  return v.empty() ? fallback : std::atof(v.c_str());
}

bool starts_with(const std::string& s, const std::string& p) {
  return s.rfind(p, 0) == 0;
}

}  // namespace

CostReport run_cost_wire(const std::string& text) {
  PricingConfig cfg;
  CostReport report;

  std::istringstream stream(text);
  std::string line;
  while (std::getline(stream, line)) {
    if (line.empty()) {
      continue;
    }
    const auto sep = line.find('=');
    if (sep == std::string::npos) {
      continue;
    }
    const std::string key = line.substr(0, sep);
    const std::string value = line.substr(sep + 1);

    if (key == "gpu_usd_per_hr") {
      cfg.gpu_usd_per_hr = parse_double(value, cfg.gpu_usd_per_hr);
    } else if (key == "electricity_usd_per_kwh") {
      cfg.electricity_usd_per_kwh = parse_double(value, cfg.electricity_usd_per_kwh);
    } else if (key == "grid_g_per_kwh") {
      cfg.grid_g_per_kwh = parse_double(value, cfg.grid_g_per_kwh);
    } else if (key == "default_in_per_1k") {
      cfg.default_price.in_per_1k = parse_double(value, 0.0);
    } else if (key == "default_out_per_1k") {
      cfg.default_price.out_per_1k = parse_double(value, 0.0);
    } else if (starts_with(key, "price.")) {
      // price.<model>.in_per_1k / price.<model>.out_per_1k
      const std::string rest = key.substr(6);
      const auto dot = rest.rfind('.');
      if (dot != std::string::npos) {
        const std::string model = rest.substr(0, dot);
        const std::string field = rest.substr(dot + 1);
        if (field == "in_per_1k") {
          cfg.model_prices[model].in_per_1k = parse_double(value, 0.0);
        } else if (field == "out_per_1k") {
          cfg.model_prices[model].out_per_1k = parse_double(value, 0.0);
        }
      }
    } else if (key == "event") {
      UsageEvent ev;
      std::istringstream fields(value);
      std::string field;
      while (std::getline(fields, field, ';')) {
        const auto fsep = field.find('=');
        if (fsep == std::string::npos) {
          continue;
        }
        const std::string fk = field.substr(0, fsep);
        const std::string fv = field.substr(fsep + 1);
        if (fk == "tenant") {
          ev.tenant = fv;
        } else if (fk == "model") {
          ev.model = fv;
        } else if (fk == "in") {
          ev.in_tokens = std::atoll(fv.c_str());
        } else if (fk == "out") {
          ev.out_tokens = std::atoll(fv.c_str());
        } else if (fk == "gpu_s") {
          ev.gpu_seconds = std::atof(fv.c_str());
        } else if (fk == "wh") {
          ev.energy_wh = std::atof(fv.c_str());
        }
      }
      report.per_tenant[ev.tenant].add(ev, cfg);
      report.per_model[ev.model].add(ev, cfg);
      report.total.add(ev, cfg);
    }
  }
  return report;
}

}  // namespace tryops
