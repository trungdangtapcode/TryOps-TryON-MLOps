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
