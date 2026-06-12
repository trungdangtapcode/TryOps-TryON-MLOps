# Supply Chain Evidence

Date: 2026-06-11

TryOps now records local supply-chain evidence without requiring network access or commercial tooling.

## Evidence Command

Run:

```bash
make supply-chain-sample
make model-supply-chain-sample
make native-ci-contract-sample
```

Artifacts:

```text
requirements.lock
artifacts/eval/supply_chain/dependency_lock.json
artifacts/eval/supply_chain/sbom.spdx.json
artifacts/eval/supply_chain/supply_chain_report.json
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

- Direct project dependencies from `pyproject.toml` pinned into `requirements.lock`.
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

## Current Tooling Status

`make vulnerability-scan-sample` builds a native Go scanner runner at
`artifacts/native/tryops_vuln_scan`. In this workspace it runs the available `npm audit` check for
`web/` and writes:

- `artifacts/eval/security/vulnerability_scan_report.json`
- `artifacts/eval/security/npm_audit_web.json`

The latest local run found 0 npm vulnerabilities, but coverage is still `partial` and
`production_ready=false`. Syft, Trivy, Grype, pip-audit, gitleaks, osv-scanner, and Cosign are not
installed in this workspace, so the local fallback SBOM plus npm audit is not a replacement for a
production Syft/Trivy or Trivy-only pipeline.

PA062 CI wiring now exists in `.github/workflows/ci.yml`. The workflow builds the seven declared
image roles, requests GitHub OIDC permissions, uploads evidence artifacts, generates Syft SPDX SBOMs,
fails on HIGH/CRITICAL Trivy image findings, and signs pushed images with Cosign keyless identity on
non-PR runs. `make native-ci-contract-sample` validates that contract locally and emits
`tryops.native_ci_contract.v1`; its current local status is `production_ready=false` because Syft,
Trivy, and Cosign are not installed here.

Preferred production commands:

```bash
syft . -o spdx-json=artifacts/eval/supply_chain/syft.spdx.json
trivy fs --scanners vuln,secret,config,license --format json .
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

The local report proves that the repo can generate lock, SBOM, model-source, dataset-license,
model-artifact serialization/provenance evidence, and a partial installed-tool vulnerability scan.
It does not prove that no CVEs exist across Python, containers, OS packages, or infrastructure in
this workspace. PA062/J010 remain partial until the GitHub Actions workflow or local environment
executes Syft, Trivy, and Cosign and archives those artifacts. The current model signature is local
offline evidence; production Sigstore keyless OIDC and Rekor transparency-log inclusion still require
OpenSSF Model Signing / Sigstore tooling.
