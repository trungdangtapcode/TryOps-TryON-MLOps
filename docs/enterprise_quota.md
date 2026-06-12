# Enterprise Quota Control

Date: 2026-06-11

TryOps now includes a usage-based quota gate for the two product workloads:

- LLM generation: requests per day and estimated tokens per day
- VTON generation: requests per day

The production-facing admission implementation now lives in the Rust gateway:

- `POST /v1/quota/check` applies per-user, per-plan daily request/token limits.
- `GET /v1/quota/snapshot` exposes hashed usage rows plus per-period tenant aggregates for operations evidence.
- `/api/*` proxy admission also applies a native per-key minute rate limit using `x-tryops-tenant`,
  `x-api-key`, or `x-forwarded-for` as the rate key, falling back to `anonymous`.
- `tryops-gateway quota-check` runs the same logic as a batch CLI for deterministic local samples.
- `TRYOPS_GATEWAY_QUOTA_LEDGER_PATH` optionally stores quota usage in a native file-backed ledger
  (`tryops.quota_ledger_file.v1`) so usage survives gateway or CLI process restarts.
- `TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN` optionally initializes and upserts a durable
  `tryops_quota_usage` Postgres table for billing/showback mirrors.
- `TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR` optionally mirrors accepted usage increments to a
  Valkey-compatible counter service using RESP `INCRBY` and `EXPIRE` commands.

Python still keeps a dependency-free fallback for unit tests and offline demos. In deployment, set
`TRYOPS_QUOTA_GATEWAY_URL` on the Python API to delegate quota admission to the Rust gateway.

## Plan Limits

| Plan | LLM requests/day | LLM tokens/day | VTON requests/day |
| --- | ---: | ---: | ---: |
| `free` | 20 | 5,000 | 5 |
| `team` | 500 | 250,000 | 100 |
| `enterprise` | 50,000 | 25,000,000 | 10,000 |

## API Contract

Inference requests accept:

- `user_id`: customer or tenant user identifier; defaults to `anonymous`
- `quota_plan`: `free`, `team`, or `enterprise`; defaults to `free`

Accepted requests include a `quota` object with:

- `allowed`
- `period`
- `user_hash`
- `plan`
- `workload`
- per-dimension checks with `limit`, `used`, `increment`, and remaining capacity
- snapshot responses include `tenants`, grouped by `period` and hashed `user_hash`, with
  per-dimension usage and `total_used`

Rejected quota requests return `status=rejected` and `error.code=quota_exceeded`.

## Privacy Boundary

The quota ledger and observability metadata store a SHA-256 derived short `user_hash`, not the raw
`user_id`. This keeps request telemetry useful for usage analysis without putting customer
identifiers into local metrics events.

## FinOps Showback

Quota usage now feeds a native-backed FinOps sample:

```bash
make finops-sample
```

The sample writes:

- `artifacts/eval/finops/unit_economics.json`
- `artifacts/eval/finops/budget_showback.json`
- `artifacts/eval/finops/semantic_cache_report.json`
- `artifacts/eval/finops/finops_report.json`

Budget decisions are keyed by hashed tenant ID and include per-plan budget utilization plus
allow/warn/block actions. The same sample writes Prometheus budget alert rules to
`infra/prometheus/tryops_finops_alerts.yml`.

## Production Path

Current native evidence:

```bash
make quota-sample
make native-quota-ledger-smoke
make native-rust-test
make native-rust-smoke
```

For a full enterprise deployment, keep the Rust admission boundary. The current compose profile can
mirror accepted usage into Postgres plus a Valkey-compatible counter service, while local smokes keep
the file ledger for deterministic offline evidence:

- Valkey atomic daily counters for hot-path windows, following the open-source Valkey
  `INCR`/`EXPIRE` counter pattern: https://valkey.io/commands/incr/
- Postgres usage ledger for billing, audit, refunds, and enterprise reporting, using upsert-style
  `INSERT ... ON CONFLICT DO UPDATE`: https://www.postgresql.org/docs/current/sql-insert.html
- Go controller reconciliation for plan changes, tenant policy, and override windows
- Prometheus metrics for quota rejects, remaining capacity bands, and high-usage tenants
- Native semantic-cache admission metrics from the Rust gateway plus hit/savings metrics joined to tenant showback

Remaining production validation is distributed multi-gateway admission, failure-mode policy for
ledger outages, backup/restore drills, and the Console/BFF quota read model.

This keeps Python in the model/control-plane path while moving admission control to the lower-level
gateway runtime.
