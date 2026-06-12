# Admin Authorization

Date: 2026-06-11

TryOps now includes a local least-privilege API-key simulation for admin actions.

This is a control-plane contract, not a production identity provider. The production direction is
OIDC/JWKS at the Rust gateway plus workload identity for runtime secrets. PA060 now adds a native
secret-rotation contract in `native/go/tryops-secret-rotation-contract/`, Vault/External Secrets
Kubernetes manifests under `infra/kubernetes/secret-management/`, and a hash-only API-key rotation
policy in `configs/secret_rotation_policy.json`; it remains plan-mode evidence until exercised
against a live Vault deployment.

## Protected Actions

The local API keeps inference public for reproducible demos and protects these admin actions:

- `POST /v1/promotion/evaluate`: requires `promotion:evaluate`
- `POST /v1/lineage`: requires `lineage:create`

Requests provide the demo credential in the payload as `api_key`. Responses include a redacted
`auth` decision with the principal key ID, role, scopes, required scope, and decision reason. Raw
keys and stored hashes are not returned by API responses or auth evidence reports.

## Demo Roles

The local registry is `configs/api_keys.json` and stores only SHA-256 hashes.

| Key label | Demo key | Role | Scopes |
| --- | --- | --- | --- |
| `admin-demo` | `tryops-admin-demo-key` | `admin` | `admin:read`, `promotion:evaluate`, `lineage:create` |
| `risk-demo` | `tryops-risk-demo-key` | `risk_reviewer` | `promotion:evaluate` |
| `viewer-demo` | `tryops-viewer-demo-key` | `viewer` | `admin:read` |

## Evidence

Run:

```bash
make auth-sample
```

Artifact:

```text
artifacts/eval/auth/api_key_auth_report.json
```

The report verifies registry hygiene and least-privilege scenarios:

- admin key can evaluate promotion and create lineage
- risk reviewer key can evaluate promotion but cannot create lineage
- viewer key cannot evaluate promotion
- missing key is rejected

For rotation-plan evidence, run:

```bash
make native-secret-rotation-contract-sample
```

Artifact:

```text
artifacts/eval/secrets/native_secret_rotation_contract.json
```
