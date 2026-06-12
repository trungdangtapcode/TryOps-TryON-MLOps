#include "tryops_cost.hpp"

#include <cmath>
#include <cstdio>
#include <string>

namespace {

int failures = 0;
void check(bool cond, const char* what) {
  if (!cond) { std::printf("FAIL: %s\n", what); failures += 1; }
}
bool approx(double a, double b) { return std::fabs(a - b) < 1e-6; }

// Single event: verify each cost component against hand arithmetic.
void test_single_event_math() {
  std::string wire =
      "gpu_usd_per_hr=3.60\nelectricity_usd_per_kwh=0.10\ngrid_g_per_kwh=400\n"
      "price.qwen.in_per_1k=0.05\nprice.qwen.out_per_1k=0.15\n"
      "event=tenant=acme;model=qwen;in=1000;out=2000;gpu_s=3600;wh=1000\n";
  auto r = tryops::run_cost_wire(wire);
  const auto& t = r.total;
  // token: 1.0*0.05 + 2.0*0.15 = 0.05 + 0.30 = 0.35
  check(approx(t.token_usd, 0.35), "token_usd");
  // gpu: 3600s/3600 * 3.60 = 3.60
  check(approx(t.gpu_usd, 3.60), "gpu_usd");
  // energy: 1000wh=1kwh * 0.10 = 0.10
  check(approx(t.energy_usd, 0.10), "energy_usd");
  check(approx(t.total_usd, 0.35 + 3.60 + 0.10), "total_usd");
  // carbon: 1kwh * 400 = 400 g
  check(approx(t.carbon_g, 400.0), "carbon_g");
}

// Attribution: two tenants split correctly; totals reconcile.
void test_tenant_split() {
  std::string wire =
      "price.m.in_per_1k=0.10\nprice.m.out_per_1k=0.10\n"
      "event=tenant=a;model=m;in=1000;out=0;gpu_s=0;wh=0\n"
      "event=tenant=b;model=m;in=2000;out=0;gpu_s=0;wh=0\n";
  auto r = tryops::run_cost_wire(wire);
  check(approx(r.per_tenant["a"].token_usd, 0.10), "tenant a cost");
  check(approx(r.per_tenant["b"].token_usd, 0.20), "tenant b cost");
  check(approx(r.total.token_usd, 0.30), "total reconciles");
  check(r.per_tenant["a"].requests == 1 && r.per_tenant["b"].requests == 1,
        "request counts");
  check(approx(r.per_model["m"].token_usd, 0.30), "per-model reconciles");
}

// Unknown model falls back to default pricing (zero unless set).
void test_default_price() {
  std::string wire =
      "default_in_per_1k=0.02\ndefault_out_per_1k=0.02\n"
      "event=tenant=x;model=unknown;in=1000;out=1000;gpu_s=0;wh=0\n";
  auto r = tryops::run_cost_wire(wire);
  check(approx(r.total.token_usd, 0.04), "default price applied");
}

// Empty stream yields zeros.
void test_empty() {
  auto r = tryops::run_cost_wire("");
  check(r.total.requests == 0 && approx(r.total.total_usd, 0.0), "empty zeros");
}

}  // namespace

int main() {
  test_single_event_math();
  test_tenant_split();
  test_default_price();
  test_empty();
  if (failures == 0) { std::printf("ok: all cost tests passed\n"); return 0; }
  std::printf("FAILED: %d cost checks\n", failures);
  return 1;
}
