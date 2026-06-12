# API Contract

Date: 2026-06-11

## Versioning Rules

The stable local API prefix is `/v1`.

Rules:

- New production-facing endpoints must be added under `/v1`.
- Existing `/v1` response fields may be added, but required field names must not be renamed in place.
- Breaking changes require a new version prefix.
- Unversioned endpoints may remain as local compatibility aliases, but demos and tests should use `/v1`.
- The Rust edge gateway exposes `/api/*` for the product surface and maps it to the backend `/v1/*`
  contract. Gateway admin paths require `x-tryops-artifact-signed: true`, and the gateway injects
  `x-request-id` when callers omit it.

## Core Endpoints

- `GET /v1/health`: process health.
- `GET /v1/ready`: local component readiness and degraded/unverified dependency state.
- `GET /v1/metrics`: Prometheus-compatible metrics text.
- `POST /v1/vton/infer`: local VTON inference through safe model aliases.
- `POST /v1/vton/jobs`: submit a local async VTON generation job.
- `GET /v1/vton/jobs/{job_id}`: inspect async VTON job status and final result.
- `POST /v1/llm/generate`: local LLM inference through safe model aliases.
- `POST /v1/promotion/evaluate`: promotion gate evaluation.
- `POST /v1/lineage`: lineage record creation.

## Admin Authorization

Inference endpoints remain public for local reproducible demos. Admin actions require a scoped
demo API key in the request payload:

- `POST /v1/promotion/evaluate`: requires `api_key` with `promotion:evaluate`
- `POST /v1/lineage`: requires `api_key` with `lineage:create`

Local demo keys:

- `tryops-admin-demo-key`: role `admin`; scopes `admin:read`, `promotion:evaluate`, `lineage:create`
- `tryops-risk-demo-key`: role `risk_reviewer`; scope `promotion:evaluate`
- `tryops-viewer-demo-key`: role `viewer`; scope `admin:read`

Rejected admin requests return `error.code=unauthorized_admin_action` and attach a redacted `auth`
decision with `reason=missing_api_key`, `invalid_api_key`, or `missing_scope`.

The local key registry stores SHA-256 hashes only in `configs/api_keys.json`. Production should
replace the simulation with OIDC, workload identity, or gateway-level secret validation.

## Request IDs

Every inference request accepts `request_id`.

If absent, the API creates one. Responses include the effective `request_id`.

## Tenant Usage Fields

Every inference request may include:

- `user_id`: customer or tenant user identifier; defaults to `anonymous`
- `quota_plan`: `free`, `team`, or `enterprise`; defaults to `free`

Successful inference responses include a `quota` object with the quota period, hashed user ID, plan,
workload, and per-dimension usage checks. The API stores and reports `user_hash`, not raw `user_id`.

## Timeout Field

Every synchronous inference request may include `timeout_ms`.

Rules:

- default: `30000`
- minimum: `1`
- maximum: `300000`

Timed-out requests return `status=rejected`, `error.code=timeout_exceeded`, and a detail block with
the configured timeout and measured elapsed time.

## Structured Errors

Rejected requests return:

```json
{
  "api_version": "v1",
  "request_id": "req-demo",
  "status": "rejected",
  "workload": "llm",
  "error": {
    "code": "invalid_llm_request",
    "message": "LLM request validation failed",
    "details": [
      {"field": "prompt", "message": "prompt is required and must be a non-empty string"}
    ]
  }
}
```

Quota rejections use the same envelope with `error.code=quota_exceeded` and attach the failed
`quota` decision so clients can see the limit, current usage, attempted increment, and remaining
capacity.

Timeout rejections use `error.code=timeout_exceeded`.

## Safe Model Selection

Clients choose model variants through aliases, not filesystem paths or arbitrary adapter names.

Supported aliases:

- VTON: `baseline`, `champion`, `challenger`, `candidate`
- LLM: `baseline`, `champion`, `challenger`, `candidate`

Current local adapters:

- VTON aliases route to `naive-overlay-vton`
- LLM aliases route to `tryops-rule-baseline`

## Routing Modes

`routing_mode=direct` uses the requested alias.

`routing_mode=canary` deterministically routes by `request_id` and `canary_percent`:

- requests inside the canary bucket use `challenger`
- other requests use `champion`

LLM requests may set `shadow=true` to run the non-primary alias and return shadow metrics without
changing the primary answer.

LLM requests may set `fallback_enabled=true`. When the requested optimized alias is not healthy,
the serving layer switches the primary alias to `baseline` and returns a `routing.fallback` block
with the pre-fallback alias, health status, and reason. The local API simulates optimized model
readiness with `optimized_available=true|false`.

## LLM Semantic Cache

LLM requests may include:

- `semantic_cache_enabled`: boolean, defaults to `true`
- `semantic_cache_threshold`: cosine-match threshold between `0` and `1`, defaults to `0.72`

The cache runs after ingress guardrails and quota admission, but before generation. Responses may
include a `semantic_cache` block with:

- lookup hit/miss, score, threshold, matched entry ID, and query fingerprint
- native C++ availability and return code
- estimated tokens, cost, and energy saved

Prompts that required PII redaction are not stored in the runtime cache.

## Async VTON Jobs

`POST /v1/vton/jobs` accepts the same payload as `POST /v1/vton/infer`, validates it, and returns an
accepted job record:

```json
{
  "schema_version": "tryops.job.v1",
  "job_id": "job-demo",
  "status": "accepted",
  "workload": "vton",
  "queue_depth": 1
}
```

`GET /v1/vton/jobs/{job_id}` returns `queued`, `running`, `completed`, or `failed`. Completed jobs
include the same result shape as the synchronous VTON endpoint.

## Local VTON File Limits

Local VTON inference accepts PNG and JPEG paths and rejects images above 10 MiB before running the
adapter. This is the local equivalent of upload size enforcement for the production gateway.

## Endpoint Smoke Test

Run:

```bash
make endpoint-smoke-sample
```

Artifact:

```text
artifacts/eval/endpoint_smoke/deployed_endpoint_smoke.json
```

The smoke report exercises:

- `GET /v1/ready`
- `POST /v1/llm/generate`
- `POST /v1/vton/infer`
- `GET /v1/metrics`

By default the smoke runner calls the local FastAPI route handlers in process so it remains
deterministic in constrained environments. To test a live deployed API, run
`PYTHONPATH=src python scripts/smoke_deployed_endpoints.py --base-url http://127.0.0.1:8000`.
