# Valkey vs Redis

Last reviewed: 2026-06-13

## Short Answer

Valkey and Redis are both in-memory key-value data stores used for caching, counters, queues, streams, rate limits, pub/sub, and low-latency application state.

For this project, Valkey is the better default because TryOps uses it as infrastructure plumbing for hot quota/rate counters, and Valkey keeps a permissive BSD license with neutral Linux Foundation governance.

## Quick Comparison

| Area | Valkey | Redis |
| --- | --- | --- |
| Origin | Community fork of Redis after the 2024 Redis licensing change. | Original project and commercial product line from Redis. |
| Governance | Linux Foundation-backed open source project. | Vendor-led by Redis. |
| License | BSD licensed. | Redis 8+ is tri-licensed: RSALv2, SSPLv1, or AGPLv3. Redis 7.4 used RSALv2/SSPLv1. |
| API compatibility | Designed to stay compatible with legacy Redis OSS behavior and clients where practical. | Native Redis API. |
| Data model | Strings, hashes, lists, sets, sorted sets, streams, bitmaps, hyperloglogs, geospatial indexes, etc. | Same core Redis data model plus Redis-specific product features depending on edition/version. |
| Common uses | Cache, message queue, streaming engine, counters, locks, session state, rate limits. | Same. |
| Managed cloud support | Available from multiple cloud/vendor ecosystems. | Available from Redis and many managed Redis-compatible providers. |
| Best fit | Teams that want Redis-compatible behavior with permissive open source licensing and foundation governance. | Teams that want Redis upstream features, Redis Cloud/Enterprise integration, or are comfortable with Redis licensing. |

## Licensing Difference

The practical difference is licensing and governance.

Valkey:

- BSD licensed.
- Linux Foundation-backed.
- Good fit when permissive open source licensing matters.

Redis:

- Redis 8+ offers RSALv2, SSPLv1, and AGPLv3 license options.
- AGPLv3 is open source, but it has network copyleft obligations.
- RSALv2 and SSPLv1 are source-available options with restrictions that require legal review for managed service or embedded platform use cases.

If a project only needs a Redis-compatible cache/counter store, Valkey reduces licensing ambiguity.

## Operational Difference

For normal application use, the operational model is similar:

```text
application
  -> client library
  -> Valkey or Redis endpoint
  -> in-memory data with optional persistence/replication
```

Both can support:

- low-latency reads/writes
- TTL keys
- atomic increments
- pub/sub
- streams
- Lua scripting
- persistence
- replication
- cluster mode

Migration is usually straightforward for common cache/counter/session workloads, but should still be tested because newer versions can diverge in commands, modules, performance behavior, and managed-service defaults.

## Which One Should TryOps Use?

Use Valkey for TryOps by default.

Reason:

```text
TryOps gateway
  -> needs fast hot quota/rate counters
  -> does not require Redis-specific commercial features
  -> benefits from permissive open source infrastructure
  -> Valkey is Redis-compatible enough for this role
```

Use Redis instead only if there is a clear need for:

- Redis Cloud or Redis Enterprise features
- a Redis-only module or command
- an existing Redis operational standard
- vendor support from Redis
- confirmed compatibility requirements from another system

## TryOps Usage

In this project, Valkey is used as a fast counter/cache-like service:

```text
Rust gateway
  -> quota/rate/admission checks
  -> Postgres durable quota ledger
  -> Valkey hot counters
  -> FastAPI if accepted
```

Postgres remains the durable source of truth. Valkey is used for fast, high-frequency state where low latency matters.

## Decision Matrix

| Requirement | Prefer |
| --- | --- |
| Permissive open source license | Valkey |
| Linux Foundation governance | Valkey |
| Redis Cloud/Enterprise product integration | Redis |
| Drop-in cache/counter service | Valkey |
| Existing Redis-only operations model | Redis |
| Avoid AGPL/SSPL/RSAL review for infrastructure plumbing | Valkey |
| Need latest Redis-specific product features | Redis |

## Sources

- Valkey homepage: https://valkey.io/
- Valkey introduction: https://valkey.io/topics/introduction/
- Redis licenses: https://redis.io/legal/licenses/
- Redis 8 GA announcement: https://redis.io/blog/redis-8-ga/
