# Chaos Reliability Drill

Date: 2026-06-11

TryOps now has a deterministic SRE chaos drill for the ML serving path.

Run:

```bash
make chaos-sample
```

Evidence:

- `native/cpp/tryops_chaos/src/tryops_chaos_cli.cpp`
- `artifacts/native/tryops_chaos_cli`
- `artifacts/eval/chaos/chaos_drill_report.json`
- `artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/auto_rollback_record.json`
- `artifacts/deployments/rollback_state.json`

## Faults Covered

The drill covers the Theme-R required failures:

- GPU OOM / resource exhaustion
- Slow LLM decode
- Corrupted model weights
- Poisoned candidate quality or safety regression

Each scenario has a steady-state hypothesis, an expected signal, bad-event count, and total-event
window. The native C++ `tryops_chaos` engine emits `tryops.native_chaos.v1`.

## Burn-Rate Gate

Each injected scenario is fed into the existing native C++ `tryops_burn_rate` engine. A scenario
requires rollback only when:

- the scenario is marked rollback-required by the native chaos evaluator, and
- the native burn-rate verdict is `page`.

This follows the same multi-window, multi-burn-rate model used by the SLO report.

## Auto Rollback

When page-level burn-rate thresholds fire, the drill calls the existing rollback path and records:

- `rollback_record.json`
- `auto_rollback_record.json`
- `rollback_state.json`

The rollback reason lists the scenario IDs that crossed the threshold. The local action is a record
of alias restoration; in Kubernetes, the same decision should be reconciled by the Go controller or
Argo Rollouts/KServe routing.

## Research Basis

- Google SRE Workbook, "Alerting on SLOs": https://sre.google/workbook/alerting-on-slos/
- Chaos Mesh documentation: https://chaos-mesh.org/docs/
- LitmusChaos project: https://litmuschaos.io/

## Production Path

The local drill is intentionally deterministic. Production should map the same scenarios to
controlled Kubernetes experiments:

- Chaos Mesh or LitmusChaos CRDs for pod kill, network delay, CPU/memory pressure, and IO faults.
- Model-loader corruption drills in staging only.
- Guardrail/promotion poisoned-candidate drills against shadow traffic.
- Automated rollback through the Go controller after burn-rate gates page.
