# Dashboard Design

## Implemented Grafana Dashboards

Provisioning files:

- `infra/grafana/provisioning/datasources/prometheus.yml`
- `infra/grafana/provisioning/dashboards/tryops.yml`
- `infra/grafana/dashboards/`

Local validation:

```bash
make dashboard-sample
```

The Grafana provider loads dashboard JSON from `/var/lib/grafana/dashboards`, which is mounted from
`infra/grafana/dashboards` in the local Compose stack. The Prometheus datasource has the stable UID
`prometheus`, so dashboard targets do not depend on Grafana-generated datasource IDs.

### TryOps Service Overview

File: `infra/grafana/dashboards/tryops-service-overview.json`

- API request rate.
- API error ratio.
- Average API latency.
- Process memory.
- Async VTON queue depth.
- Firing alerts.
- Gateway request rate.
- Gateway p95 latency from native histogram buckets.
- Gateway rate-limit rejects and upstream proxy errors.

### TryOps Model Quality

File: `infra/grafana/dashboards/tryops-model-quality.json`

- LLM quality score.
- VTON garment similarity.
- LLM latency p95.
- VTON latency.
- LLM output throughput.
- Completed inference rate by model alias.

### TryOps Cost and Capacity

File: `infra/grafana/dashboards/tryops-cost-capacity.json`

- Estimated daily request cost.
- Estimated hourly cost run rate.
- Quota utilization.
- Daily request volume.
- Daily LLM token volume.
- Semantic-cache hit rate.
- Semantic-cache cost saved.
- Tenant budget utilization.
- Energy per 1k tokens.
- CO2e per 1k tokens.
- Cost vs energy correlation.
- Cost and capacity evidence map.

### TryOps Observability Drilldown

File: `infra/grafana/dashboards/tryops-observability-drilldown.json`

The production operations view uses the same visual structure as a dense infrastructure dashboard:

- A first-row KPI strip with colored stat tiles for platform health, API error ratio, active VTON jobs, FASHN model-service errors, telemetry export failures, and log/trace storage health.
- A health row with scrape-target status, Loki/Tempo readiness, and Valkey runtime behavior.
- A telemetry row for OTel collector throughput and TryOps OTel bridge export flow.
- A runtime row for API memory, job queue pressure, quota keys, and gateway request/error flow.
- A log row for FASHN VTON service logs, async job lifecycle logs, and all structured error logs.

This dashboard is meant for debugging live production behavior. Raw backend logs stay in Grafana/Loki; the product UI should surface sanitized job status, request IDs, job IDs, and user-safe error summaries.

## Future Dashboard Views

### Executive Demo

- Current champion model for VTON and LLM.
- Latest promotion decision.
- Pass/fail gates.
- p50/p95 latency.
- Cost estimate.
- Open incidents.

### Expanded Model Quality

- VTON garment fidelity.
- VTON identity preservation.
- VTON artifact rate.
- LLM quality score.
- LLM tokens/sec.
- LLM memory footprint.

### MLOps Operations

- Pipeline run history.
- Data validation pass/fail.
- Promotion approvals.
- Registry alias changes.
- Rollback events.
- Reproducibility status.

### Risk and Security

- Risk status by model candidate.
- OWASP LLM risk tests.
- Vulnerability counts.
- SBOM availability.
- Signed artifact status.
- Missing governance artifacts.
