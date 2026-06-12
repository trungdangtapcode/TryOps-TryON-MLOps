from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from tryops.quota import user_hash
from tryops.semantic_cache import SemanticCacheEntry, lookup_semantic_cache


UNIT_ECONOMICS_SCHEMA = "tryops.unit_economics.v1"
BUDGET_SHOWBACK_SCHEMA = "tryops.budget_showback.v1"
SEMANTIC_CACHE_REPORT_SCHEMA = "tryops.semantic_cache_report.v1"
FINOPS_REPORT_SCHEMA = "tryops.finops_report.v1"


@dataclass(frozen=True)
class FinOpsConfig:
    llm_node_hourly_usd: float = 0.55
    vton_node_hourly_usd: float = 0.90
    vton_seconds_per_request: float = 2.5
    free_daily_budget_usd: float = 0.01
    team_daily_budget_usd: float = 25.0
    enterprise_daily_budget_usd: float = 1000.0
    warn_ratio: float = 0.80
    block_ratio: float = 1.00
    semantic_cache_threshold: float = 0.60

    def daily_budget_for_plan(self, plan: str) -> float:
        budgets = {
            "free": self.free_daily_budget_usd,
            "team": self.team_daily_budget_usd,
            "enterprise": self.enterprise_daily_budget_usd,
        }
        return float(budgets.get(str(plan).lower(), self.free_daily_budget_usd))


def build_finops_report(
    *,
    benchmark: dict[str, Any],
    quota_report: dict[str, Any],
    semantic_cache_report: dict[str, Any],
    usage_events: list[dict[str, Any]] | None = None,
    config: FinOpsConfig | None = None,
) -> dict[str, Any]:
    cfg = config or FinOpsConfig()
    unit_economics = build_unit_economics(benchmark=benchmark, config=cfg)
    showback = build_budget_showback(
        quota_report=quota_report,
        usage_events=usage_events or default_usage_events(),
        unit_economics=unit_economics,
        semantic_cache_report=semantic_cache_report,
        config=cfg,
    )
    return {
        "schema_version": FINOPS_REPORT_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "unit_economics": unit_economics,
        "semantic_cache": semantic_cache_report,
        "budget_showback": showback,
        "promotion_gate_input": {
            "passed": not any(decision["action"] == "block" for decision in showback["budget_decisions"]),
            "warning_count": sum(1 for decision in showback["budget_decisions"] if decision["action"] == "warn"),
            "blocked_tenants": [
                decision["tenant_hash"] for decision in showback["budget_decisions"] if decision["action"] == "block"
            ],
        },
        "production_path": {
            "hot_path": "native C++ semantic-cache lookup now; Rust gateway or C++ sidecar can call the same wire contract",
            "durable_ledger": "replace local sample usage with Redis atomic counters plus Postgres billing/showback ledger",
            "vector_index": "replace lexical demo embeddings with a neural embedding model and FAISS/Qdrant when available",
        },
    }


def build_unit_economics(*, benchmark: dict[str, Any], config: FinOpsConfig | None = None) -> dict[str, Any]:
    cfg = config or FinOpsConfig()
    records = list(benchmark.get("records", []))
    total_input_tokens = sum(int(record.get("input_tokens", 0)) for record in records)
    total_output_tokens = sum(int(record.get("output_tokens", 0)) for record in records)
    total_tokens = total_input_tokens + total_output_tokens
    total_latency_ms = sum(float(record.get("latency_ms", 0.0)) for record in records)
    summary = benchmark.get("summary", {}) if isinstance(benchmark.get("summary"), dict) else {}
    observed_tokens_per_second = float(summary.get("tokens_per_second", 0.0) or 0.0)
    if observed_tokens_per_second <= 0.0 and total_latency_ms > 0.0:
        observed_tokens_per_second = total_output_tokens / max(total_latency_ms / 1000.0, 0.001)
    llm_cost_per_1k_tokens = (
        cfg.llm_node_hourly_usd / (observed_tokens_per_second * 3600.0) * 1000.0
        if observed_tokens_per_second > 0.0
        else 0.0
    )
    vton_cost_per_request = cfg.vton_node_hourly_usd * cfg.vton_seconds_per_request / 3600.0
    return {
        "schema_version": UNIT_ECONOMICS_SCHEMA,
        "pricing_model": {
            "basis": "open-source self-hosted hardware run-rate model",
            "llm_node_hourly_usd": cfg.llm_node_hourly_usd,
            "vton_node_hourly_usd": cfg.vton_node_hourly_usd,
            "vton_seconds_per_request": cfg.vton_seconds_per_request,
        },
        "llm": {
            "record_count": len(records),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "observed_tokens_per_second": round(observed_tokens_per_second, 6),
            "cost_per_1k_tokens_usd": round(llm_cost_per_1k_tokens, 9),
            "sample_cost_usd": round(total_tokens / 1000.0 * llm_cost_per_1k_tokens, 9),
        },
        "vton": {
            "cost_per_request_usd": round(vton_cost_per_request, 9),
        },
    }


def evaluate_semantic_cache_workload(
    *,
    entries: list[SemanticCacheEntry],
    queries: list[dict[str, Any]],
    threshold: float = 0.72,
    cli_path: str | None = None,
) -> dict[str, Any]:
    results = []
    for query in queries:
        lookup = lookup_semantic_cache(
            query=str(query["prompt"]),
            entries=entries,
            threshold=threshold,
            cli_path=cli_path,
        )
        expected_hit = bool(query.get("expected_hit", False))
        observed_hit = bool(lookup.get("lookup", {}).get("hit", False))
        results.append(
            {
                "id": str(query["id"]),
                "expected_hit": expected_hit,
                "observed_hit": observed_hit,
                "passed": expected_hit == observed_hit,
                "lookup": lookup["lookup"],
                "savings": lookup["savings"],
                "native_available": bool(lookup.get("available", False)),
            }
        )
    hit_count = sum(1 for result in results if result["observed_hit"])
    total_tokens_saved = sum(int(result["savings"]["tokens_saved"]) for result in results)
    total_cost_saved = sum(float(result["savings"]["cost_saved_usd"]) for result in results)
    total_energy_saved = sum(float(result["savings"]["energy_saved_wh"]) for result in results)
    return {
        "schema_version": SEMANTIC_CACHE_REPORT_SCHEMA,
        "threshold": float(threshold),
        "entry_count": len(entries),
        "query_count": len(results),
        "hit_count": hit_count,
        "miss_count": len(results) - hit_count,
        "hit_rate": round(hit_count / len(results), 6) if results else 0.0,
        "tokens_saved": total_tokens_saved,
        "cost_saved_usd": round(total_cost_saved, 9),
        "energy_saved_wh": round(total_energy_saved, 9),
        "native_available": any(result["native_available"] for result in results),
        "passed": all(result["passed"] for result in results),
        "results": results,
    }


def build_budget_showback(
    *,
    quota_report: dict[str, Any],
    usage_events: list[dict[str, Any]],
    unit_economics: dict[str, Any],
    semantic_cache_report: dict[str, Any],
    config: FinOpsConfig | None = None,
) -> dict[str, Any]:
    cfg = config or FinOpsConfig()
    llm_cost_per_1k = float(unit_economics["llm"]["cost_per_1k_tokens_usd"])
    vton_cost_per_request = float(unit_economics["vton"]["cost_per_request_usd"])
    showback = []
    for event in usage_events:
        llm_tokens = int(event.get("llm_tokens", 0))
        vton_requests = int(event.get("vton_requests", 0))
        plan = str(event.get("plan", "free")).lower()
        tenant_hash = user_hash(str(event.get("tenant_id", "anonymous")))
        gross_spend = (llm_tokens / 1000.0 * llm_cost_per_1k) + (vton_requests * vton_cost_per_request)
        cache_credit = float(event.get("cache_credit_usd", 0.0))
        net_spend = max(0.0, gross_spend - cache_credit)
        budget = cfg.daily_budget_for_plan(plan)
        utilization = net_spend / budget if budget > 0.0 else 0.0
        action = "allow"
        if utilization >= cfg.block_ratio:
            action = "block"
        elif utilization >= cfg.warn_ratio:
            action = "warn"
        showback.append(
            {
                "tenant_hash": tenant_hash,
                "plan": plan,
                "active_users": int(event.get("active_users", 1)),
                "llm_tokens": llm_tokens,
                "llm_requests": int(event.get("llm_requests", 0)),
                "vton_requests": vton_requests,
                "gross_spend_usd": round(gross_spend, 9),
                "cache_credit_usd": round(cache_credit, 9),
                "net_spend_usd": round(net_spend, 9),
                "daily_budget_usd": round(budget, 9),
                "budget_utilization": round(utilization, 6),
                "action": action,
            }
        )
    quota_snapshot = quota_report.get("snapshot", {}) if isinstance(quota_report.get("snapshot"), dict) else {}
    quota_usage_rows = quota_snapshot.get("usage", []) if isinstance(quota_snapshot.get("usage"), list) else []
    return {
        "schema_version": BUDGET_SHOWBACK_SCHEMA,
        "quota_snapshot_rows": len(quota_usage_rows),
        "cache_savings_credit_usd": round(float(semantic_cache_report.get("cost_saved_usd", 0.0)), 9),
        "budget_policy": {
            "warn_ratio": cfg.warn_ratio,
            "block_ratio": cfg.block_ratio,
            "daily_budgets_usd": {
                "free": cfg.free_daily_budget_usd,
                "team": cfg.team_daily_budget_usd,
                "enterprise": cfg.enterprise_daily_budget_usd,
            },
        },
        "tenant_showback": showback,
        "budget_decisions": [
            {
                "tenant_hash": row["tenant_hash"],
                "plan": row["plan"],
                "budget_utilization": row["budget_utilization"],
                "action": row["action"],
                "reason": _budget_reason(row["action"]),
            }
            for row in showback
        ],
    }


def default_usage_events() -> list[dict[str, Any]]:
    return [
        {
            "tenant_id": "demo-free",
            "plan": "free",
            "active_users": 1,
            "llm_requests": 6,
            "llm_tokens": 4200,
            "vton_requests": 3,
        },
        {
            "tenant_id": "design-team",
            "plan": "team",
            "active_users": 18,
            "llm_requests": 420,
            "llm_tokens": 220000,
            "vton_requests": 80,
        },
        {
            "tenant_id": "enterprise-fashion",
            "plan": "enterprise",
            "active_users": 540,
            "llm_requests": 18000,
            "llm_tokens": 8200000,
            "vton_requests": 2600,
        },
    ]


def entries_from_benchmark(benchmark: dict[str, Any], *, llm_cost_per_1k_tokens_usd: float, energy_wh_per_1k_tokens: float) -> list[SemanticCacheEntry]:
    entries = []
    for record in benchmark.get("records", []):
        prompt = str(record.get("prompt", ""))
        input_tokens = int(record.get("input_tokens", 0))
        output_tokens = int(record.get("output_tokens", 0))
        total_tokens = input_tokens + output_tokens
        generation = {
            "schema_version": "tryops.llm_generation.v1",
            "status": "completed",
            "model": record.get("model", {}),
            "prompt": {
                "characters": len(prompt),
                "estimated_tokens": input_tokens,
                "class": "semantic_cache_seed",
            },
            "output": {
                "text": str(record.get("output_text", "")),
                "estimated_tokens": output_tokens,
                "truncated": False,
            },
            "metrics": {
                "latency_ms": float(record.get("latency_ms", 0.0)),
                "tokens_per_second": float(record.get("tokens_per_second", 0.0)),
                "memory_gb": float(record.get("memory_gb", 0.0)),
            },
            "cost_estimate": {
                "request_usd": total_tokens / 1000.0 * llm_cost_per_1k_tokens_usd,
                "total_tokens": total_tokens,
                "basis": "semantic cache benchmark seed",
            },
            "safety": record.get("safety", {}),
            "structured_answer": record.get("structured_answer", {}),
        }
        entries.append(
            SemanticCacheEntry(
                id=f"bench-{record.get('id', len(entries))}",
                prompt=f"model=baseline structured=True prompt={prompt}",
                generation=generation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=total_tokens / 1000.0 * llm_cost_per_1k_tokens_usd,
                energy_wh=total_tokens / 1000.0 * energy_wh_per_1k_tokens,
            )
        )
    return entries


def default_semantic_cache_queries() -> list[dict[str, Any]]:
    return [
        {
            "id": "cache-hit-mlops-summary",
            "prompt": "model=baseline structured=True prompt=Explain TryOps MLOps core in bullet points.",
            "expected_hit": True,
        },
        {
            "id": "cache-hit-quantization",
            "prompt": "model=baseline structured=True prompt=Compare GPTQ AWQ quantization latency memory quality.",
            "expected_hit": True,
        },
        {
            "id": "cache-miss-budget-gate",
            "prompt": "model=baseline structured=True prompt=How should an enterprise tenant budget gate work?",
            "expected_hit": False,
        },
    ]


def attach_cache_credit_to_usage(usage_events: list[dict[str, Any]], semantic_cache_report: dict[str, Any]) -> list[dict[str, Any]]:
    if not usage_events:
        return []
    credit = float(semantic_cache_report.get("cost_saved_usd", 0.0))
    updated = [dict(event) for event in usage_events]
    updated[0]["cache_credit_usd"] = credit
    return updated


def _budget_reason(action: str) -> str:
    if action == "block":
        return "projected daily spend exceeds the tenant budget"
    if action == "warn":
        return "projected daily spend is above the warning threshold"
    return "projected daily spend is inside budget"
