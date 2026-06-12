// TryOps native cost-attribution (FinOps showback/chargeback) engine.
//
// Turns a per-request usage stream (tokens, GPU-seconds, energy) into auditable
// per-tenant and per-model cost + carbon breakdowns. The arithmetic lives in a
// compiled engine so chargeback numbers are exact and reproducible at the
// boundary, consistent with the green-MLOps energy methodology
// (GPU $/hr dominates; electricity and carbon priced from grid intensity).
#ifndef TRYOPS_COST_HPP
#define TRYOPS_COST_HPP

#include <cstdint>
#include <map>
#include <string>

namespace tryops {

struct ModelPrice {
  double in_per_1k = 0.0;   // USD per 1k input tokens
  double out_per_1k = 0.0;  // USD per 1k output tokens
};

struct PricingConfig {
  double gpu_usd_per_hr = 2.50;
  double electricity_usd_per_kwh = 0.12;
  double grid_g_per_kwh = 475.0;
  ModelPrice default_price{0.0, 0.0};
  std::map<std::string, ModelPrice> model_prices;

  const ModelPrice& price_for(const std::string& model) const;
};

struct UsageEvent {
  std::string tenant;
  std::string model;
  std::int64_t in_tokens = 0;
  std::int64_t out_tokens = 0;
  double gpu_seconds = 0.0;
  double energy_wh = 0.0;
};

struct CostBucket {
  std::int64_t requests = 0;
  std::int64_t in_tokens = 0;
  std::int64_t out_tokens = 0;
  double token_usd = 0.0;
  double gpu_usd = 0.0;
  double energy_usd = 0.0;
  double total_usd = 0.0;
  double carbon_g = 0.0;

  void add(const UsageEvent& ev, const PricingConfig& cfg);
};

struct CostReport {
  std::map<std::string, CostBucket> per_tenant;
  std::map<std::string, CostBucket> per_model;
  CostBucket total;
};

CostReport run_cost_wire(const std::string& text);

}  // namespace tryops

#endif  // TRYOPS_COST_HPP
