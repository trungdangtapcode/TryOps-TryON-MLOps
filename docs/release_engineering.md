# Release Engineering

Date: 2026-06-11

## Deployment Profiles

Local deployment profiles live in:

- `configs/deploy/staging.json`
- `configs/deploy/production-demo.json`

Both profiles use `/v1`, manual approval, safe model aliases, and promotion evidence checks.

## Package Command

Create a deployment package from promotion evidence:

```bash
make deploy-package-sample
```

This writes:

```text
artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/
```

Key files:

- `deployment_manifest.json`
- `release_notes.md`
- `rollback_plan.json`
- `gitops/application.yaml`
- `gitops/rollout.yaml`
- `gitops/services.yaml`
- `gitops/kustomization.yaml`
- `gitops/gitops_validation.json`

The promotion evidence feeding the package also includes:

- `native_policy_decision.json`
- `openlineage_run_event.json`
- `openlineage_validation.json`

Deployment manifests carry whether the native C++ policy decision matched the Python policy gate and
whether the OpenLineage RunEvent and GitOps manifests passed native validation.

## Signed Promotion PR Trigger

Exercise the signed promotion-PR controller trigger:

```bash
make signed-pr-promotion-sample
```

This target starts the Go controller, sends a GitHub-style signed `pull_request.closed` event, verifies
the `X-Hub-Signature-256` HMAC over the raw payload, and records accepted promotion actions only when
the PR is merged and carries code-owner approval, verified-commit, status-check, promotion, native
policy, OpenLineage, GitOps, and model-provenance evidence.

Evidence:

- `native/go/tryops-controller/*.go`
- `scripts/simulate_signed_pr_promotion.py`
- `artifacts/eval/signed_pr/signed_pr_promotion_report.json`

The local accepted action list is:

- verify the signed GitHub pull-request webhook
- validate the promotion PR
- promote the candidate to the target stage
- sync the registry alias

Production hardening should replace the local embedded check fields with GitHub API lookups for
reviews, branch protection, commit verification, and check-suite conclusions.

## Registry Webhook Deploy Trigger

Exercise the signed registry-webhook deployment trigger:

```bash
make registry-webhook-sample
```

This target starts the Go controller, sends a signed MLflow-style `model_version_alias.created`
event, verifies the HMAC signature/freshness headers, and records the accepted deployment actions.

Evidence:

- `native/go/tryops-controller/*.go`
- `scripts/simulate_registry_webhook.py`
- `artifacts/eval/registry_webhook/registry_webhook_report.json`

The local accepted action list is:

- verify the signed registry webhook
- load the deployment package
- trigger GitOps sync
- start an Argo Rollouts canary

## Rollback Drill

Record a rollback drill:

```bash
make rollback-sample
```

This writes:

- `rollback_record.json` inside the package directory
- `artifacts/deployments/rollback_state.json`

The rollback command records the release state locally. In a Kubernetes profile, the same manifest
would drive alias restoration through the Go controller or KServe routing.

## Chaos Auto Rollback

Run the native-backed SRE chaos drill:

```bash
make chaos-sample
```

This evaluates injected GPU OOM, slow decode, corrupted weights, and poisoned-candidate scenarios
against the native C++ burn-rate engine. When page thresholds fire, the sample reuses the existing
rollback mechanism and writes `auto_rollback_record.json` plus the global `rollback_state.json`.

## Release Notes

Every deployment package includes release notes with:

- profile
- model name/version/alias
- promotion decision
- model metrics
- artifact URIs
- rollback command

This satisfies the local release-log requirement while keeping the final Kubernetes release path open.
