# Model Governance

## Required Artifacts

Every promoted candidate must have:

- Model card
- Data card
- Evaluation report
- SBOM
- Model artifact scan
- Model provenance attestation

## Required Evidence

- Metrics pass workload-specific thresholds.
- Candidate artifact is signed.
- Model weights are SafeTensors-only and pass the native model scanner.
- Model provenance verifies with the native C++ provenance verifier before load.
- Promotion emits an OpenLineage RunEvent and validates the event envelope with the native C++ OpenLineage validator.
- Deployment packages include Argo CD / Argo Rollouts manifests and native C++ GitOps validation evidence.
- Promotion PR automation accepts only signed GitHub-style webhook deliveries verified by the Go controller, with merged PR, approval, verified-commit, status-check, and provenance evidence.
- Deployment automation accepts only signed registry-webhook events verified by the Go controller before GitOps/canary actions are issued; when `TRYOPS_CONTROLLER_POLICY_CLI` is configured, the controller also re-runs the native C++ promotion policy over the webhook `policy_candidate` and fails closed on rejection or execution failure.
- Critical and high vulnerabilities are zero for champion promotion.
- Risk status is `low` or `medium_approved`.
- Champion promotion has `mlops_owner` and `risk_owner` approval.
- Dependency lockfile, SBOM, model-source, and dataset-license evidence are generated before release review.
- Major project risks are mapped to NIST AI RMF functions.
- LLM controls are mapped to OWASP Top 10 for LLM Applications 2025.
- Responsible-AI residual risks are visible in the final report.
- Promotion and lineage admin actions require least-privilege API-key authorization.

## Candidate States

- `candidate`: produced but not trusted.
- `challenger`: passed staging gates and can be shadow tested.
- `champion`: production-demo model alias.
- `rejected`: failed a policy gate.
- `archived`: kept for lineage, no longer served.

## Governance Evidence

Run:

```bash
make governance-sample
```

Artifact:

```text
artifacts/eval/governance/governance_report.json
```

Admin authorization evidence:

```bash
make auth-sample
```

```text
artifacts/eval/auth/api_key_auth_report.json
```

Supply-chain evidence:

```bash
make supply-chain-sample
make model-supply-chain-sample
```

```text
requirements.lock
artifacts/eval/supply_chain/sbom.spdx.json
artifacts/eval/supply_chain/supply_chain_report.json
artifacts/eval/model_supply_chain/model_supply_chain_report.json
artifacts/eval/model_supply_chain/model_provenance.json
reports/generated/vton-catvton-2026-06-11-001/openlineage_run_event.json
reports/generated/vton-catvton-2026-06-11-001/openlineage_validation.json
artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/gitops/gitops_validation.json
artifacts/eval/signed_pr/signed_pr_promotion_report.json
artifacts/eval/registry_webhook/registry_webhook_report.json
```
