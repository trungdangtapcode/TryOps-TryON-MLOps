#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.contracts import ModelCandidate  # noqa: E402
from tryops.model_provenance import (  # noqa: E402
    IN_TOTO_STATEMENT_TYPE,
    SLSA_PROVENANCE_PREDICATE_TYPE,
    build_model_provenance,
)
from tryops.native_model_scan import scan_model_artifacts, write_minimal_safetensors  # noqa: E402
from tryops.native_policy import evaluate_with_native_policy, native_decision_matches_python  # noqa: E402
from tryops.policy import evaluate_promotion  # noqa: E402


SCHEMA_VERSION = "tryops.model_supply_chain_report.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate model artifact supply-chain gates.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/model_supply_chain/model_supply_chain_report.json"))
    parser.add_argument("--sample-dir", type=Path, default=Path("artifacts/eval/model_supply_chain/samples"))
    parser.add_argument("--native-scan-cli", type=Path, default=Path("artifacts/native/tryops_model_scan_cli"))
    parser.add_argument("--native-policy-cli", type=Path, default=Path("artifacts/native/tryops_policy_cli"))
    args = parser.parse_args()

    samples = _write_samples(args.sample_dir)
    safe_scan = scan_model_artifacts(samples["safe"], cli_path=args.native_scan_cli)
    unsafe_scan = scan_model_artifacts(samples["unsafe"], cli_path=args.native_scan_cli)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_name("safe_model_artifact_scan.json").write_text(
        json.dumps(safe_scan, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.output.with_name("unsafe_model_artifact_scan.json").write_text(
        json.dumps(unsafe_scan, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    safe_provenance = build_model_provenance(
        candidate_id="llm-safe-safetensors-2026-06-11",
        workload="llm",
        model_name="tryops-demo-llm",
        model_version="0.1.0",
        model_artifact_paths=[path for path in samples["safe"] if path.suffix == ".safetensors"],
        evidence_uris={
            "model_artifact_scan": str(args.output.with_name("safe_model_artifact_scan.json")),
            "sbom": "artifacts/eval/supply_chain/sbom.spdx.json",
            "guardrail_report": "artifacts/eval/guardrails/guardrail_report.json",
        },
        output_dir=args.output.parent,
        pipeline_run_id="run-model-supply-chain",
        signer_identity="tryops-local-ci",
    )
    safe_candidate = _candidate_from_scan(
        candidate_id="llm-safe-safetensors-2026-06-11",
        scan=safe_scan,
        scan_uri=str(args.output.with_name("safe_model_artifact_scan.json")),
        provenance=safe_provenance,
    )
    unsafe_candidate = _candidate_from_scan(
        candidate_id="llm-unsafe-pickle-2026-06-11",
        scan=unsafe_scan,
        scan_uri=str(args.output.with_name("unsafe_model_artifact_scan.json")),
        provenance=None,
    )
    safe_decision = _evaluate_candidate(safe_candidate, native_policy_cli=args.native_policy_cli)
    unsafe_decision = _evaluate_candidate(unsafe_candidate, native_policy_cli=args.native_policy_cli)

    report = {
        "schema_version": SCHEMA_VERSION,
        "policy": "safetensors_only",
        "research_basis": {
            "safetensors": "https://github.com/huggingface/safetensors",
            "huggingface_pickle_scanning": "https://huggingface.co/docs/hub/en/security-pickle",
            "modelscan": "https://github.com/protectai/modelscan",
            "fickling": "https://github.com/trailofbits/fickling",
        },
        "artifacts": {
            "safe_scan": str(args.output.with_name("safe_model_artifact_scan.json")),
            "unsafe_scan": str(args.output.with_name("unsafe_model_artifact_scan.json")),
            "model_provenance": str(args.output.with_name("model_provenance.json")),
            "model_signature_bundle": str(args.output.with_name("model_signature_bundle.json")),
            "in_toto_statement": str(args.output.with_name("model_provenance.intoto.json")),
        },
        "native_model_scan_available": bool(safe_scan.get("available")) and bool(unsafe_scan.get("available")),
        "model_provenance": {
            "schema_version": safe_provenance.get("schema_version"),
            "passed": safe_provenance.get("passed"),
            "signature_mode": safe_provenance.get("signature", {}).get("mode"),
            "sigstore_keyless_oidc": safe_provenance.get("signature", {}).get("sigstore_keyless_oidc"),
            "statement_type": safe_provenance.get("slsa", {}).get("statement_type"),
            "predicate_type": safe_provenance.get("slsa", {}).get("predicate_type"),
            "verification": safe_provenance.get("verification", {}),
        },
        "safe_scan": _scan_summary(safe_scan),
        "unsafe_scan": _scan_summary(unsafe_scan),
        "promotion_decisions": {
            "safe_candidate": safe_decision,
            "unsafe_candidate": unsafe_decision,
        },
        "passed": (
            bool(safe_scan.get("passed"))
            and not bool(unsafe_scan.get("passed"))
            and bool(safe_provenance.get("passed"))
            and safe_decision["python"]["approved"]
            and not unsafe_decision["python"]["approved"]
            and safe_decision["native"].get("matches_python", False)
            and unsafe_decision["native"].get("matches_python", False)
        ),
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


def _write_samples(sample_dir: Path) -> dict[str, list[Path]]:
    safe_dir = sample_dir / "safe"
    unsafe_dir = sample_dir / "unsafe"
    safe_dir.mkdir(parents=True, exist_ok=True)
    unsafe_dir.mkdir(parents=True, exist_ok=True)
    safe_config = safe_dir / "config.json"
    safe_config.write_text('{"model_type":"tryops-demo"}\n', encoding="utf-8")
    safe_weight = write_minimal_safetensors(safe_dir / "model.safetensors")
    unsafe_config = unsafe_dir / "config.json"
    unsafe_config.write_text('{"model_type":"tryops-demo"}\n', encoding="utf-8")
    unsafe_weight = unsafe_dir / "pytorch_model.bin"
    unsafe_weight.write_bytes(b"\x80\x04GLOBAL\nos\nsystem\n.")
    return {
        "safe": [safe_config, safe_weight],
        "unsafe": [unsafe_config, unsafe_weight],
    }


def _candidate_from_scan(
    *,
    candidate_id: str,
    scan: dict[str, Any],
    scan_uri: str,
    provenance: dict[str, Any] | None,
) -> ModelCandidate:
    summary = scan.get("summary", {})
    rejected_extensions = sorted(
        {
            str(item.get("extension", ""))
            for item in scan.get("files", [])
            if item.get("rejected") and item.get("extension")
        }
    )
    return ModelCandidate(
        candidate_id=candidate_id,
        workload="llm",
        model_name="tryops-demo-llm",
        model_version="0.1.0",
        metrics={
            "quality_score": 0.91,
            "tokens_per_second": 80.0,
            "latency_p95_ms": 120.0,
            "memory_gb": 1.5,
        },
        artifacts={
            "model_card": "reports/generated/llm/model_card.md",
            "data_card": "reports/generated/llm/data_card.md",
            "evaluation_report": "artifacts/eval/llm_baseline/benchmark.json",
            "sbom": "artifacts/eval/supply_chain/sbom.spdx.json",
            "guardrail_report": "artifacts/eval/guardrails/guardrail_report.json",
            "model_artifact_scan": scan_uri,
            **(
                {"model_provenance": str(Path(provenance["signature_bundle_uri"]).with_name("model_provenance.json"))}
                if provenance
                else {}
            ),
        },
        approvals=["mlops_owner", "risk_owner"],
        risk_status="low",
        vulnerabilities={"critical": 0, "high": 0},
        signed=bool(provenance and provenance.get("passed")),
        metadata={
            "code_version": "local",
            "dataset_version": "golden-prompts-v1",
            "pipeline_run_id": "run-model-supply-chain",
            "guardrails": {
                "status": "passed",
                "failed_cases": 0,
                "blocked_risk_ids": [],
            },
            "model_provenance": _provenance_metadata(provenance),
            "model_artifacts": {
                "serialization_policy": "safetensors_only",
                "scan_status": "passed" if scan.get("passed") else "failed",
                "unsafe_file_count": int(summary.get("unsafe_file_count", 0)),
                "safetensors_files": int(summary.get("safetensors_files", 0)),
                "rejected_extensions": rejected_extensions,
            },
        },
    )


def _provenance_metadata(provenance: dict[str, Any] | None) -> dict[str, Any]:
    if not provenance:
        return {
            "status": "missing",
            "statement_type": "missing",
            "predicate_type": "missing",
            "signature_mode": "missing",
            "signer_identity": "",
            "verified": False,
        }
    return {
        "status": "passed" if provenance.get("passed") else "failed",
        "statement_type": provenance.get("slsa", {}).get("statement_type", IN_TOTO_STATEMENT_TYPE),
        "predicate_type": provenance.get("slsa", {}).get("predicate_type", SLSA_PROVENANCE_PREDICATE_TYPE),
        "signature_mode": provenance.get("signature", {}).get("mode", "missing"),
        "signer_identity": provenance.get("signature", {}).get("signer_identity", ""),
        "verified": bool(provenance.get("verification", {}).get("passed")),
    }


def _evaluate_candidate(candidate: ModelCandidate, *, native_policy_cli: Path) -> dict[str, Any]:
    python_decision = evaluate_promotion(candidate, target_stage="champion")
    native = evaluate_with_native_policy(candidate, target_stage="champion", cli_path=native_policy_cli)
    native["matches_python"] = native_decision_matches_python(native, python_decision)
    return {
        "candidate_id": candidate.candidate_id,
        "python": python_decision.to_dict(),
        "native": native,
    }


def _scan_summary(scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": scan.get("schema_version"),
        "source": scan.get("source"),
        "available": bool(scan.get("available")),
        "passed": bool(scan.get("passed")),
        "safe_tensors_only": bool(scan.get("safe_tensors_only")),
        "summary": scan.get("summary", {}),
        "findings": scan.get("findings", []),
    }


if __name__ == "__main__":
    raise SystemExit(main())
