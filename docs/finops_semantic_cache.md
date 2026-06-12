# FinOps and Semantic Cache

Date: 2026-06-11

TryOps now has a local FinOps control loop for the LLM and VTON product workloads:

- `tryops.unit_economics.v1`: cost per 1k LLM tokens and cost per VTON request from the self-hosted hardware run-rate model.
- `tryops.budget_showback.v1`: per-tenant spend, cache credit, budget utilization, and allow/warn/block decisions.
- `tryops.semantic_cache_report.v1`: semantic-cache hit rate, tokens saved, cost saved, and energy saved.
- `tryops.native_semantic_cache.v1`: native C++ lookup verdict for the cache hot path.

Run:

```bash
make finops-sample
```

Primary evidence:

- `artifacts/eval/finops/finops_report.json`
- `artifacts/eval/finops/unit_economics.json`
- `artifacts/eval/finops/budget_showback.json`
- `artifacts/eval/finops/semantic_cache_report.json`
- `infra/prometheus/tryops_finops_alerts.yml`
- `infra/grafana/dashboards/tryops-cost-capacity.json`

## Runtime Cache Placement

`/v1/llm/generate` now evaluates the semantic cache after ingress guardrails and quota admission, but before generation. This keeps safety and quota checks authoritative while avoiding repeated generation when a tenant asks a similar prompt.

The cache is privacy-aware:

- Raw prompts are not emitted in cache metadata.
- Public metadata uses prompt fingerprints and candidate IDs.
- Prompts that required PII redaction are not stored.
- Cache hits still pass through egress guardrails before returning.

## Native Hot Path

The native C++ cache hot path is split into a reusable core and a thin CLI adapter:

```text
native/cpp/tryops_semantic_cache/include/tryops_semantic_cache.hpp
native/cpp/tryops_semantic_cache/src/tryops_semantic_cache.cpp
native/cpp/tryops_semantic_cache/src/tryops_semantic_cache_cli.cpp
native/cpp/tryops_semantic_cache/tests/test_semantic_cache.cpp
```

The verified binary is:

```text
artifacts/native/tryops_semantic_cache_cli
```

It accepts a line-based wire format with a query, threshold, and cache entries. The core computes a deterministic lexical embedding and cosine similarity, then emits `tryops.native_semantic_cache.v1`.

The Rust gateway now owns the edge admission step before the request reaches FastAPI:

```text
native/rust/tryops-gateway/src/semantic_cache.rs
```

`make native-edge-cache-smoke` proves that cacheable LLM prompts are admitted, sensitive prompts are skipped, and the gateway exports `tryops_gateway_semantic_cache_admissions_total`. When `TRYOPS_GATEWAY_SEMANTIC_CACHE_CLI` and `TRYOPS_GATEWAY_SEMANTIC_CACHE_ENTRIES` are configured, the Rust gateway invokes the native C++ CLI before proxying, returns `x-tryops-edge-cache-lookup-*` headers, and exports `tryops_gateway_semantic_cache_lookups_total`.

Production should keep this interface shape and replace the local lexical embedding with one of:

- a low-latency embedding model served by the Rust gateway or C++ sidecar,
- FAISS for in-process vector lookup,
- Qdrant or another vector service when cross-process durability is required.

## Budget Gates

The local budget gate has three actions:

- `allow`: projected spend is inside the daily tenant budget.
- `warn`: projected spend is above the warning threshold.
- `block`: projected spend reaches the hard budget limit.

Prometheus rules are generated into `infra/prometheus/tryops_finops_alerts.yml` and mounted by `docker-compose.yml`.

## Current Sample Result

The current deterministic sample reports:

- Native semantic cache available.
- 2 hits and 1 miss over the cache workload.
- 132 tokens saved.
- Cost and energy savings credited back to tenant showback.
- No tenant exceeds the default daily budget.

## Production Path

For enterprise deployment:

- Keep quota and cache admission in the Rust gateway.
- Use Valkey-compatible atomic counters for hot daily quota and budget checks.
- Use Postgres `tryops_quota_usage` upserts for the durable billing/showback ledger.
- Export `tryops_budget_utilization_ratio`, `tryops_request_cost_usd`, edge cache-admission metrics, and cache hit/savings metrics from the gateway or billing service.
- Keep Python for model evaluation and report generation, not the serving hot path.
