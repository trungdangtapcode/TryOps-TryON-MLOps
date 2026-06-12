#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.finops import (  # noqa: E402
    FinOpsConfig,
    attach_cache_credit_to_usage,
    build_finops_report,
    build_unit_economics,
    default_semantic_cache_queries,
    default_usage_events,
    entries_from_benchmark,
    evaluate_semantic_cache_workload,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate TryOps FinOps, budget, and semantic-cache controls.")
    parser.add_argument("--benchmark", type=Path, default=Path("artifacts/eval/llm_baseline/benchmark.json"))
    parser.add_argument("--quota", type=Path, default=Path("artifacts/eval/quota/quota_usage.json"))
    parser.add_argument("--energy", type=Path, default=Path("artifacts/eval/energy/energy_sweep.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/finops/finops_report.json"))
    parser.add_argument("--native-cache-cli", type=Path, default=Path("artifacts/native/tryops_semantic_cache_cli"))
    parser.add_argument("--rules-output", type=Path, default=Path("infra/prometheus/tryops_finops_alerts.yml"))
    args = parser.parse_args()

    benchmark = _read_json(args.benchmark)
    quota_report = _read_json(args.quota)
    config = FinOpsConfig()
    unit_economics = build_unit_economics(benchmark=benchmark, config=config)
    entries = entries_from_benchmark(
        benchmark,
        llm_cost_per_1k_tokens_usd=float(unit_economics["llm"]["cost_per_1k_tokens_usd"]),
        energy_wh_per_1k_tokens=_energy_wh_per_1k_tokens(args.energy),
    )
    semantic_cache = evaluate_semantic_cache_workload(
        entries=entries,
        queries=default_semantic_cache_queries(),
        threshold=config.semantic_cache_threshold,
        cli_path=str(args.native_cache_cli),
    )
    usage_events = attach_cache_credit_to_usage(default_usage_events(), semantic_cache)
    report = build_finops_report(
        benchmark=benchmark,
        quota_report=quota_report,
        semantic_cache_report=semantic_cache,
        usage_events=usage_events,
        config=config,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (args.output.parent / "unit_economics.json").write_text(
        json.dumps(report["unit_economics"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output.parent / "semantic_cache_report.json").write_text(
        json.dumps(report["semantic_cache"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output.parent / "budget_showback.json").write_text(
        json.dumps(report["budget_showback"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.rules_output.parent.mkdir(parents=True, exist_ok=True)
    args.rules_output.write_text(_finops_alert_rules(), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["semantic_cache"]["passed"] and report["promotion_gate_input"]["passed"] else 1


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _energy_wh_per_1k_tokens(path: Path) -> float:
    if not path.exists():
        return 0.0
    report = _read_json(path)
    variants = report.get("variants", [])
    if not isinstance(variants, list):
        return 0.0
    for variant in variants:
        if isinstance(variant, dict) and variant.get("variant") == "none":
            return float(variant.get("energy_wh_per_1k_tokens", 0.0) or 0.0)
    return 0.0


def _finops_alert_rules() -> str:
    return """groups:
- name: tryops-finops-alerts
  rules:
  - alert: TryOpsTenantBudgetWarning
    expr: max(tryops_budget_utilization_ratio) > 0.8
    for: 15m
    labels:
      severity: warning
      workload: finops
    annotations:
      summary: Tenant projected spend is above the budget warning threshold
      runbook_url: docs/finops_semantic_cache.md
  - alert: TryOpsTenantBudgetHardLimit
    expr: max(tryops_budget_utilization_ratio) >= 1.0
    for: 5m
    labels:
      severity: page
      workload: finops
    annotations:
      summary: Tenant projected spend reached the hard budget limit
      runbook_url: docs/finops_semantic_cache.md
  - alert: TryOpsSemanticCacheHitRateLow
    expr: sum(rate(tryops_semantic_cache_requests_total{result=\"hit\"}[1h])) / clamp_min(sum(rate(tryops_semantic_cache_requests_total[1h])), 1) < 0.2
    for: 30m
    labels:
      severity: warning
      workload: llm
    annotations:
      summary: LLM semantic-cache hit rate is below the expected optimization threshold
      runbook_url: docs/finops_semantic_cache.md
"""


if __name__ == "__main__":
    raise SystemExit(main())
