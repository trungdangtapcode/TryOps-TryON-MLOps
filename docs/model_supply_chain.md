# Model Supply Chain Gate

Date: 2026-06-11

TryOps now enforces SafeTensors-only model artifacts plus signed provenance before promotion. The
production intent is simple: model files that can execute code through Python pickle-style
deserialization do not pass the gate, and accepted model weights must be bound to a provenance
statement that can be verified before load.

## Native Scanner

Path:

```text
native/cpp/tryops_model_scan/src/tryops_model_scan_cli.cpp
```

Build and run the evidence sample:

```bash
make model-supply-chain-sample
```

The sample creates two local candidates:

- safe candidate: `config.json` + valid tiny `model.safetensors`
- unsafe candidate: `config.json` + `pytorch_model.bin`

The native scanner emits:

```text
tryops.native_model_scan.v1
```

The model supply-chain report emits:

```text
tryops.model_supply_chain_report.v1
```

Artifacts:

- `artifacts/native/tryops_model_scan_cli`
- `artifacts/native/tryops_model_provenance_cli`
- `artifacts/eval/model_supply_chain/model_supply_chain_report.json`
- `artifacts/eval/model_supply_chain/safe_model_artifact_scan.json`
- `artifacts/eval/model_supply_chain/unsafe_model_artifact_scan.json`
- `artifacts/eval/model_supply_chain/model_provenance.json`
- `artifacts/eval/model_supply_chain/model_provenance.intoto.json`
- `artifacts/eval/model_supply_chain/model_signature_bundle.json`

## Provenance And Signature Evidence

The safe candidate now emits:

- `tryops.model_provenance.v1`
- an in-toto Statement with `predicateType: https://slsa.dev/provenance/v1`
- a DSSE-shaped local signature bundle
- native C++ verification evidence from `tryops_model_provenance_cli`

The local signature mode is `local-dsse-digest`: it hashes the in-toto payload and model artifact
digest so the offline sample can prove artifact binding without external identity services. It does
not claim Sigstore keyless OIDC or Rekor transparency-log inclusion. Production should replace this
with OpenSSF Model Signing / Sigstore model-transparency keyless signing.

## Promotion Gate

Promotion candidates for `vton` and `llm` workloads must include:

```json
{
  "artifacts": {
    "model_artifact_scan": "artifacts/eval/model_supply_chain/safe_model_artifact_scan.json",
    "model_provenance": "artifacts/eval/model_supply_chain/model_provenance.json"
  },
  "metadata": {
    "model_provenance": {
      "status": "passed",
      "statement_type": "https://in-toto.io/Statement/v1",
      "predicate_type": "https://slsa.dev/provenance/v1",
      "signature_mode": "local-dsse-digest",
      "signer_identity": "tryops-local-ci",
      "verified": true
    },
    "model_artifacts": {
      "serialization_policy": "safetensors_only",
      "scan_status": "passed",
      "unsafe_file_count": 0,
      "safetensors_files": 1,
      "rejected_extensions": []
    }
  }
}
```

The Python policy gate, the C++ policy gate, and the Rego policy sketch all enforce the same scan and
provenance fields. The native policy bridge uses flattened metadata keys such as:

```text
metadata.model_provenance.predicate_type=https://slsa.dev/provenance/v1
metadata.model_provenance.verified=true
metadata.model_artifacts.serialization_policy=safetensors_only
metadata.model_artifacts.scan_status=passed
```

## Rejection Policy

The scanner rejects:

- `.bin`
- `.pt`
- `.pth`
- `.ckpt`
- `.pkl`
- `.pickle`
- `.joblib`
- active or graph formats requiring explicit review such as `.h5`, `.keras`, `.pb`, `.onnx`, `.tflite`
- unknown model artifact extensions
- invalid SafeTensors headers

Safe support files such as `config.json`, tokenizer files, and metadata files can accompany a
SafeTensors weight file.

## Research Basis

- SafeTensors implements a simple tensor storage format designed to be safe compared with pickle and fast through zero-copy loading: https://github.com/huggingface/safetensors
- Hugging Face documents pickle security scanning and notes that pickle exploits require separate checks beyond antivirus scanning: https://huggingface.co/docs/hub/en/security-pickle
- Protect AI ModelScan is an open-source scanner for unsafe code in model files across multiple ML formats: https://github.com/protectai/modelscan
- Trail of Bits Fickling provides pickle decompilation/static analysis and ML pickle allowlist checks: https://github.com/trailofbits/fickling
- OpenSSF Model Signing supports signing and verification of ML models using Sigstore or other PKI while preserving a Sigstore bundle-style format: https://openssf.org/projects/model-signing/
- Sigstore model-transparency signs model file digests in a DSSE/in-toto-shaped bundle and verifies by recomputing model file hashes: https://github.com/sigstore/model-transparency
- in-toto Statements bind artifact subjects to predicate types; SLSA provenance is one such predicate type: https://slsa.dev/blog/2023/05/in-toto-and-slsa
