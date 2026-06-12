from __future__ import annotations

import base64
import json
import os
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


MODEL_PROVENANCE_SCHEMA = "tryops.model_provenance.v1"
LOCAL_SIGNATURE_BUNDLE_SCHEMA = "tryops.local_model_signature_bundle.v1"
IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
SLSA_PROVENANCE_PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
DEFAULT_NATIVE_PROVENANCE_CLI = Path("artifacts/native/tryops_model_provenance_cli")


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_model_provenance(
    *,
    candidate_id: str,
    workload: str,
    model_name: str,
    model_version: str,
    model_artifact_paths: list[str | Path],
    evidence_uris: dict[str, str],
    output_dir: str | Path,
    pipeline_run_id: str,
    source_repository: str = "local-workspace",
    source_ref: str = "local-dev-unversioned",
    source_commit: str = "local-dev-unversioned",
    human_approver: str = "risk_owner",
    signer_identity: str = "tryops-local-ci",
    key_id: str = "tryops-local-dev-key",
    verifier_cli_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create an offline model-signing and provenance evidence bundle.

    This deliberately mirrors the Sigstore/DSSE/in-toto/SLSA data shape while recording that the
    local signature is a deterministic offline digest, not a real keyless OIDC/Rekor signature.
    """

    artifacts = [Path(path) for path in model_artifact_paths]
    subjects = [
        {
            "name": str(path),
            "digest": {"sha256": sha256_file(path)},
            "size_bytes": path.stat().st_size,
        }
        for path in artifacts
    ]
    if not subjects:
        raise ValueError("model provenance requires at least one model artifact")

    created_at = datetime.now(UTC).isoformat()
    statement = {
        "_type": IN_TOTO_STATEMENT_TYPE,
        "subject": [{"name": item["name"], "digest": item["digest"]} for item in subjects],
        "predicateType": SLSA_PROVENANCE_PREDICATE_TYPE,
        "predicate": {
            "buildDefinition": {
                "buildType": "https://tryops.local/build/model-supply-chain/v1",
                "externalParameters": {
                    "candidate_id": candidate_id,
                    "workload": workload,
                    "model_name": model_name,
                    "model_version": model_version,
                    "source_repository": source_repository,
                    "source_ref": source_ref,
                    "human_approver": human_approver,
                },
                "internalParameters": {
                    "offline_evidence": True,
                    "tool": "tryops.model_provenance",
                    "signature_mode": "local-dsse-digest",
                },
                "resolvedDependencies": [
                    {
                        "name": "source",
                        "uri": source_repository,
                        "digest": {"gitCommit": source_commit},
                    },
                    *[
                        {
                            "name": name,
                            "uri": uri,
                            "digest": _artifact_uri_digest(uri),
                        }
                        for name, uri in sorted(evidence_uris.items())
                        if uri
                    ],
                ],
            },
            "runDetails": {
                "builder": {"id": "https://tryops.local/builders/model-supply-chain"},
                "metadata": {
                    "invocationId": pipeline_run_id,
                    "startedOn": created_at,
                    "finishedOn": created_at,
                },
            },
        },
    }
    statement_bytes = canonical_json_bytes(statement)
    payload_b64 = base64.b64encode(statement_bytes).decode("ascii")
    payload_sha256 = sha256(statement_bytes).hexdigest()
    signature_value = _local_signature_value(key_id=key_id, payload_b64=payload_b64)

    primary_subject = subjects[0]
    bundle = {
        "schema_version": LOCAL_SIGNATURE_BUNDLE_SCHEMA,
        "created_at": created_at,
        "payload_type": DSSE_PAYLOAD_TYPE,
        "payload_b64": payload_b64,
        "payload_sha256": payload_sha256,
        "subject_name": primary_subject["name"],
        "subject_sha256": primary_subject["digest"]["sha256"],
        "subject_count": len(subjects),
        "statement_type": IN_TOTO_STATEMENT_TYPE,
        "predicate_type": SLSA_PROVENANCE_PREDICATE_TYPE,
        "signature": {
            "algorithm": "sha256-local-digest",
            "key_id": key_id,
            "signer_identity": signer_identity,
            "value": signature_value,
        },
        "sigstore": {
            "model_transparency_compatible_shape": True,
            "keyless_oidc": False,
            "rekor_transparency_log": False,
            "reason": "offline evidence bundle; install OpenSSF model-signing for real Sigstore verification",
        },
    }

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    statement_path = output / "model_provenance.intoto.json"
    bundle_path = output / "model_signature_bundle.json"
    provenance_path = output / "model_provenance.json"
    statement_path.write_text(json.dumps(statement, indent=2, sort_keys=True), encoding="utf-8")
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")

    verification = verify_model_signature_bundle(
        artifact_path=primary_subject["name"],
        bundle_path=bundle_path,
        expected_signer_identity=signer_identity,
        cli_path=verifier_cli_path or DEFAULT_NATIVE_PROVENANCE_CLI,
    )
    provenance = {
        "schema_version": MODEL_PROVENANCE_SCHEMA,
        "created_at": created_at,
        "candidate_id": candidate_id,
        "workload": workload,
        "model": {
            "name": model_name,
            "version": model_version,
        },
        "subjects": subjects,
        "statement_uri": str(statement_path),
        "signature_bundle_uri": str(bundle_path),
        "signature": {
            "mode": "local-dsse-digest",
            "signed": True,
            "signer_identity": signer_identity,
            "key_id": key_id,
            "sigstore_keyless_oidc": False,
            "rekor_transparency_log": False,
        },
        "slsa": {
            "statement_type": IN_TOTO_STATEMENT_TYPE,
            "predicate_type": SLSA_PROVENANCE_PREDICATE_TYPE,
            "build_type": statement["predicate"]["buildDefinition"]["buildType"],
            "builder_id": statement["predicate"]["runDetails"]["builder"]["id"],
        },
        "evidence": dict(evidence_uris),
        "verification": verification,
        "research_basis": {
            "openssf_model_signing": "https://openssf.org/projects/model-signing/",
            "sigstore_model_transparency": "https://github.com/sigstore/model-transparency",
            "slsa_provenance": "https://slsa.dev/provenance/v1",
            "in_toto_statement": "https://in-toto.io/",
        },
        "passed": bool(verification.get("passed")),
    }
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
    return provenance


def verify_model_signature_bundle(
    *,
    artifact_path: str | Path,
    bundle_path: str | Path,
    expected_signer_identity: str = "",
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_MODEL_PROVENANCE_CLI", DEFAULT_NATIVE_PROVENANCE_CLI))
    if path.exists():
        wire = "\n".join(
            [
                f"artifact_path={artifact_path}",
                f"bundle_path={bundle_path}",
                f"expected_signer_identity={expected_signer_identity}",
                f"expected_predicate_type={SLSA_PROVENANCE_PREDICATE_TYPE}",
                "",
            ]
        )
        completed = subprocess.run(
            [str(path)],
            input=wire,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if completed.returncode in {0, 2} and completed.stdout.strip():
            result = json.loads(completed.stdout)
            result["cli_path"] = str(path)
            return result
        return {
            "schema_version": "tryops.native_model_provenance.v1",
            "available": True,
            "source": "native_cpp_cli",
            "cli_path": str(path),
            "passed": False,
            "errors": [completed.stderr.strip() or completed.stdout.strip() or "native verifier failed"],
            "returncode": completed.returncode,
        }
    return _verify_model_signature_bundle_fallback(
        artifact_path=artifact_path,
        bundle_path=bundle_path,
        expected_signer_identity=expected_signer_identity,
    )


def _verify_model_signature_bundle_fallback(
    *,
    artifact_path: str | Path,
    bundle_path: str | Path,
    expected_signer_identity: str,
) -> dict[str, Any]:
    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    errors: list[str] = []
    subject_sha = str(bundle.get("subject_sha256", ""))
    artifact_sha = sha256_file(artifact_path)
    payload_b64 = str(bundle.get("payload_b64", ""))
    payload_sha = sha256(base64.b64decode(payload_b64.encode("ascii"))).hexdigest() if payload_b64 else ""
    signature = dict(bundle.get("signature", {}))
    expected_signature = _local_signature_value(
        key_id=str(signature.get("key_id", "")),
        payload_b64=payload_b64,
    )
    if artifact_sha != subject_sha:
        errors.append("artifact sha256 does not match signed subject")
    if payload_sha != str(bundle.get("payload_sha256", "")):
        errors.append("payload sha256 does not match bundle")
    if expected_signature != str(signature.get("value", "")):
        errors.append("local signature digest does not match payload")
    if str(bundle.get("predicate_type", "")) != SLSA_PROVENANCE_PREDICATE_TYPE:
        errors.append("predicate type is not SLSA provenance v1")
    if expected_signer_identity and str(signature.get("signer_identity", "")) != expected_signer_identity:
        errors.append("signer identity mismatch")
    return {
        "schema_version": "tryops.native_model_provenance.v1",
        "available": False,
        "source": "python_fallback",
        "passed": not errors,
        "errors": errors,
        "checks": {
            "artifact_sha256": artifact_sha,
            "subject_sha256": subject_sha,
            "payload_sha256": payload_sha,
            "signature_algorithm": str(signature.get("algorithm", "")),
            "signer_identity": str(signature.get("signer_identity", "")),
        },
    }


def _local_signature_value(*, key_id: str, payload_b64: str) -> str:
    return sha256(f"{key_id}\n{payload_b64}".encode("utf-8")).hexdigest()


def _artifact_uri_digest(uri: str) -> dict[str, str]:
    path = Path(uri)
    if path.exists() and path.is_file():
        return {"sha256": sha256_file(path)}
    return {"uriSha256": sha256(uri.encode("utf-8")).hexdigest()}
