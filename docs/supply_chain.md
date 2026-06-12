# Supply Chain Evidence

Date: 2026-06-11

TryOps now records local supply-chain evidence without requiring network access or commercial tooling.

## Evidence Command

Run:

```bash
make supply-chain-sample
make model-supply-chain-sample
make native-dependency-lock-contract-sample
make native-ci-contract-live
```

Artifacts:

```text
uv.lock
requirements.lock
artifacts/eval/supply_chain/dependency_lock.json
artifacts/eval/supply_chain/sbom.spdx.json
artifacts/eval/ci/live_supply_chain_report.json
artifacts/eval/ci/native_ci_contract.json
artifacts/eval/supply_chain/supply_chain_report.json
artifacts/eval/dependencies/native_dependency_lock_contract.json
artifacts/eval/model_supply_chain/model_supply_chain_report.json
artifacts/eval/model_supply_chain/safe_model_artifact_scan.json
artifacts/eval/model_supply_chain/unsafe_model_artifact_scan.json
artifacts/eval/model_supply_chain/model_provenance.json
artifacts/eval/model_supply_chain/model_provenance.intoto.json
artifacts/eval/model_supply_chain/model_signature_bundle.json
artifacts/eval/ci/native_ci_contract.json
.github/workflows/ci.yml
```

## What The Report Covers

- Full Python project resolution pinned in `uv.lock`, including the ML packages that previously
  drifted during benchmark runs (`accelerate` and `bitsandbytes`).
- Native Go dependency-lock contract over `uv.lock`, `web/package-lock.json`, Rust `Cargo.lock`, and
  Go `go.mod`/`go.sum` checksum coverage.
- Legacy local fallback dependency export in `requirements.lock` for the existing SPDX fallback.
- Installed local package versions when present.
- Lower-bound pins for optional or runtime dependencies not installed in this workspace.
- SPDX 2.3 JSON SBOM generated from the dependency lock plus model and dataset source inventories.
- Tool availability checks for Syft, Trivy, Grype, and pip-audit.
- Local hygiene findings for pre-release packages and missing local distributions.
- Model-source license inventory from `configs/model_sources.json`.
- Dataset license and usage restrictions from `configs/dataset_licenses.json`.
- Native C++ model artifact scan evidence for SafeTensors-only model promotion.
- Local in-toto/SLSA-shaped model provenance and DSSE-shaped signature evidence.
- Native C++ model provenance verification before promotion.
- Python, C++, and Rego promotion gates requiring a passing model artifact scan and model provenance.
- GitHub Actions CI contract for language tests, seven container image roles, Syft SBOM generation,
  Trivy HIGH/CRITICAL scan gating, uploaded evidence artifacts, and Cosign keyless signing.
- Native live supply-chain evidence from pinned Syft, Trivy, and Cosign containers, with a signed
  SPDX SBOM blob verified locally before the CI contract can report production readiness.

## Current Tooling Status

`make vulnerability-scan-sample` builds a native Go scanner runner at
`artifacts/native/tryops_vuln_scan`. In this workspace it runs the available `npm audit` check for
`web/` and writes:

- `artifacts/eval/security/vulnerability_scan_report.json`
- `artifacts/eval/security/npm_audit_web.json`

The latest local `vulnerability-scan-sample` run found 0 npm vulnerabilities, but that specific
fallback report remains `coverage=partial` and `production_ready=false` because it only runs tools
installed on the host. It remains useful as a fast local smoke check and explicit missing-tool
inventory.

PA062 CI wiring now exists in `.github/workflows/ci.yml`. The workflow builds the seven declared
image roles, requests GitHub OIDC permissions, uploads evidence artifacts, generates Syft SPDX SBOMs,
fails on HIGH/CRITICAL Trivy image findings, and signs pushed images with Cosign keyless identity on
non-PR runs. `make native-live-supply-chain-sample` executes `anchore/syft:v1.45.1`,
`aquasec/trivy:0.71.0`, and `ghcr.io/sigstore/cosign/cosign:v2.4.1` as pinned containers, so host
PATH installation is not required. The latest live report is `tryops.live_supply_chain.v1` with 613
Syft packages, 0 HIGH/CRITICAL Trivy vulnerability/misconfiguration/secret findings, and a verified
Cosign signature over `artifacts/eval/ci/syft/filesystem.spdx.json`. `make native-ci-contract-live`
validates the full contract locally and emits `tryops.native_ci_contract.v1` with
`production_ready=true`.

Preferred production commands:

```bash
syft . -o spdx-json=artifacts/eval/supply_chain/syft.spdx.json
trivy fs --scanners vuln,secret,config,license --format json .
make native-ci-contract-live
```

Syft is the preferred open-source SBOM generator for filesystems and supports SPDX/CycloneDX output.
Trivy's filesystem target scans local projects for vulnerabilities, secrets, misconfigurations, and
licenses, and can also generate SBOMs.

## Model Source Pins

The local executable adapters are pinned to repository paths and covered by the project Apache-2.0
license:

- `tryops-rule-baseline`: `src/tryops/pipelines/llm_baseline.py`
- `naive-overlay-vton`: `src/tryops/pipelines/vton_baseline.py`

The first neural LLM target is recorded as:

- `HuggingFaceTB/SmolLM2-135M-Instruct`
- revision: `12fd25f`
- license: `Apache-2.0`

The model weights are not downloaded or executed by the local evidence command.

## Model Artifact Gate

`make model-supply-chain-sample` builds `artifacts/native/tryops_model_scan_cli`, creates safe and
unsafe local model artifact samples, and proves:

- a valid `.safetensors` model artifact passes the scanner and promotion gates
- the safe model artifact is bound to `tryops.model_provenance.v1`, an in-toto/SLSA provenance
  statement, and a local DSSE-shaped signature bundle
- `artifacts/native/tryops_model_provenance_cli` verifies the model artifact digest, payload digest,
  signer identity, and SLSA predicate before promotion
- a `.bin` pickle-family model artifact fails the scanner
- the unsafe candidate is rejected by both the Python and native C++ promotion gates with matching reasons

See `docs/model_supply_chain.md` for the exact schema and policy contract.

## Dataset Restrictions

- `tryops-synthetic-demo`: local generated demo data, usable for smoke evidence only.
- `VITON-HD`: CC-BY-NC-4.0, research/non-commercial only.
- `Dress Code`: custom non-commercial academic license; not released to private companies.
- `user-uploaded-images`: transient inference input only; no training or persistence without consent.

## Residual Risk

The local reports now prove that the repo can generate lock, SBOM, model-source, dataset-license,
model-artifact serialization/provenance evidence, a partial installed-tool vulnerability scan, and
live Syft/Trivy/Cosign execution through pinned containers. Residual risk remains for optional
secondary scanners (Grype, pip-audit, gitleaks, osv-scanner) and for public keyless model
transparency: the current model signature is local offline evidence; production Sigstore keyless OIDC
and Rekor transparency-log inclusion still require OpenSSF Model Signing / Sigstore tooling.
