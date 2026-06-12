# Rollback and Fallback Design

## Model Alias Strategy

- `candidate`: produced by a run, not trusted.
- `challenger`: passed staging gates and can receive shadow traffic.
- `champion`: production-demo alias.
- `rejected`: failed policy.
- `archived`: kept for lineage only.

## Rollback

Rollback means restoring the previous `champion` alias. The rollout log must record:

- Previous champion.
- Failed candidate.
- Reason for rollback.
- Operator or automated trigger.
- Timestamp.
- Follow-up issue.

## Fallback

VTON fallback:

- Use cached seeded outputs with authentic lineage.
- Display degraded-mode status.
- Keep upload validation active.

LLM fallback:

- Route from optimized candidate to baseline.
- If no model is available, serve cached benchmark examples.
- Record fallback as an operational event.

## Incident Drill

1. Promote bad candidate to staging only.
2. Run shadow traffic.
3. Trigger latency or quality alert.
4. Reject candidate.
5. Generate incident note.
6. Confirm champion alias remains unchanged.

## Automated Chaos Rollback

`make chaos-sample` runs deterministic GPU OOM, slow-decode, corrupted-weight, and poisoned-candidate
faults through the native chaos evaluator and native burn-rate engine. When a scenario crosses a
page-level burn-rate threshold, TryOps reuses the same rollback record path and writes:

- `artifacts/eval/chaos/chaos_drill_report.json`
- `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/auto_rollback_record.json`
- `artifacts/deployments/rollback_state.json`

The local implementation records alias restoration. A production deployment should let the Go
controller or rollout controller reconcile that decision into runtime routing.
