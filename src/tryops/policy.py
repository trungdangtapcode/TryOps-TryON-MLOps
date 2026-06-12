from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tryops.contracts import ModelCandidate, PromotionDecision


DEFAULT_POLICY: dict[str, Any] = {
    "required_artifacts": ["model_card", "data_card", "evaluation_report", "sbom", "model_provenance"],
    "required_approvals": {
        "staging": ["mlops_owner"],
        "champion": ["mlops_owner", "risk_owner"],
    },
    "accepted_risk_statuses": ["low", "medium_approved"],
    "security": {
        "max_critical_vulnerabilities": 0,
        "max_high_vulnerabilities": 0,
    },
    "guardrails": {
        "required_for_workloads": ["llm"],
        "required_artifact": "guardrail_report",
        "accepted_verdicts": ["passed"],
        "max_failed_cases": 0,
    },
    "model_artifacts": {
        "required_for_workloads": ["vton", "llm"],
        "required_artifact": "model_artifact_scan",
        "serialization_policy": "safetensors_only",
        "max_unsafe_files": 0,
        "min_safetensors_files": 1,
    },
    "model_provenance": {
        "required_for_workloads": ["vton", "llm"],
        "required_artifact": "model_provenance",
        "accepted_statuses": ["passed"],
        "statement_type": "https://in-toto.io/Statement/v1",
        "predicate_type": "https://slsa.dev/provenance/v1",
        "accepted_signature_modes": ["local-dsse-digest", "sigstore-keyless-oidc"],
    },
    "metric_gates": {
        "vton": {
            "garment_fidelity": {"min": 0.72},
            "identity_preservation": {"min": 0.70},
            "artifact_rate": {"max": 0.12},
            "latency_p95_ms": {"max": 12000},
        },
        "llm": {
            "quality_score": {"min": 0.78},
            "tokens_per_second": {"min": 20},
            "latency_p95_ms": {"max": 2500},
            "memory_gb": {"max": 16},
        },
    },
}


@dataclass(frozen=True)
class GateResult:
    passed: bool
    message: str


def evaluate_promotion(
    candidate: ModelCandidate,
    *,
    target_stage: str,
    policy: dict[str, Any] | None = None,
) -> PromotionDecision:
    """Evaluate enterprise promotion gates for a model candidate."""

    policy = policy or DEFAULT_POLICY
    results = [
        _check_known_workload(candidate, policy),
        _check_required_artifacts(candidate, policy),
        _check_approvals(candidate, target_stage, policy),
        _check_risk_status(candidate, policy),
        _check_security(candidate, policy),
        _check_signature(candidate),
        _check_model_provenance(candidate, policy),
        _check_guardrails(candidate, policy),
        _check_model_artifacts(candidate, policy),
        _check_metric_gates(candidate, policy),
    ]

    failures = [result.message for result in results if not result.passed]
    warnings = _collect_warnings(candidate)
    return PromotionDecision(
        approved=not failures,
        target_stage=target_stage,
        reasons=failures or ["all promotion gates passed"],
        warnings=warnings,
    )


def _check_known_workload(candidate: ModelCandidate, policy: dict[str, Any]) -> GateResult:
    known = set(policy["metric_gates"])
    if candidate.workload not in known:
        return GateResult(False, f"unknown workload '{candidate.workload}'")
    return GateResult(True, "known workload")


def _check_required_artifacts(candidate: ModelCandidate, policy: dict[str, Any]) -> GateResult:
    missing = [
        name
        for name in policy["required_artifacts"]
        if not candidate.artifacts.get(name)
    ]
    if missing:
        return GateResult(False, f"missing required artifacts: {', '.join(missing)}")
    return GateResult(True, "required artifacts present")


def _check_approvals(
    candidate: ModelCandidate,
    target_stage: str,
    policy: dict[str, Any],
) -> GateResult:
    required = policy["required_approvals"].get(target_stage)
    if required is None:
        return GateResult(False, f"unknown target stage '{target_stage}'")
    missing = [approval for approval in required if approval not in candidate.approvals]
    if missing:
        return GateResult(False, f"missing approvals: {', '.join(missing)}")
    return GateResult(True, "approvals present")


def _check_risk_status(candidate: ModelCandidate, policy: dict[str, Any]) -> GateResult:
    if candidate.risk_status not in policy["accepted_risk_statuses"]:
        return GateResult(False, f"unaccepted risk status '{candidate.risk_status}'")
    return GateResult(True, "risk accepted")


def _check_security(candidate: ModelCandidate, policy: dict[str, Any]) -> GateResult:
    max_critical = int(policy["security"]["max_critical_vulnerabilities"])
    max_high = int(policy["security"]["max_high_vulnerabilities"])
    critical = int(candidate.vulnerabilities.get("critical", 0))
    high = int(candidate.vulnerabilities.get("high", 0))
    failures: list[str] = []
    if critical > max_critical:
        failures.append(f"critical vulnerabilities {critical} > {max_critical}")
    if high > max_high:
        failures.append(f"high vulnerabilities {high} > {max_high}")
    if failures:
        return GateResult(False, "; ".join(failures))
    return GateResult(True, "security scan within threshold")


def _check_signature(candidate: ModelCandidate) -> GateResult:
    if not candidate.signed:
        return GateResult(False, "candidate artifact is not signed")
    return GateResult(True, "candidate artifact signed")


def _check_guardrails(candidate: ModelCandidate, policy: dict[str, Any]) -> GateResult:
    guardrail_policy = policy.get("guardrails", {})
    required_workloads = set(guardrail_policy.get("required_for_workloads", []))
    if candidate.workload not in required_workloads:
        return GateResult(True, "guardrails not required for workload")
    required_artifact = str(guardrail_policy.get("required_artifact", "guardrail_report"))
    failures: list[str] = []
    if not candidate.artifacts.get(required_artifact):
        failures.append(f"missing required guardrail artifact: {required_artifact}")
    guardrail_metadata = candidate.metadata.get("guardrails", {})
    if not isinstance(guardrail_metadata, dict):
        guardrail_metadata = {}
    verdict = str(guardrail_metadata.get("status", candidate.metadata.get("guardrail_verdict", "missing")))
    accepted = set(str(item) for item in guardrail_policy.get("accepted_verdicts", ["passed"]))
    if verdict not in accepted:
        failures.append(f"unaccepted guardrail verdict '{verdict}'")
    failed_cases = int(guardrail_metadata.get("failed_cases", candidate.metadata.get("guardrail_failed_cases", 0)) or 0)
    max_failed = int(guardrail_policy.get("max_failed_cases", 0))
    if failed_cases > max_failed:
        failures.append(f"guardrail failed cases {failed_cases} > {max_failed}")
    blocked_risks = guardrail_metadata.get("blocked_risk_ids", candidate.metadata.get("guardrail_blocked_risk_ids", []))
    if blocked_risks:
        failures.append("guardrail blocked risks: " + ", ".join(str(item) for item in blocked_risks))
    if failures:
        return GateResult(False, "; ".join(failures))
    return GateResult(True, "guardrail gate passed")


def _check_model_provenance(candidate: ModelCandidate, policy: dict[str, Any]) -> GateResult:
    provenance_policy = policy.get("model_provenance", {})
    required_workloads = set(provenance_policy.get("required_for_workloads", []))
    if candidate.workload not in required_workloads:
        return GateResult(True, "model provenance not required for workload")
    required_artifact = str(provenance_policy.get("required_artifact", "model_provenance"))
    failures: list[str] = []
    if not candidate.artifacts.get(required_artifact):
        failures.append(f"missing required model provenance: {required_artifact}")
    metadata = candidate.metadata.get("model_provenance", {})
    if not isinstance(metadata, dict):
        metadata = {}
    status = str(metadata.get("status", candidate.metadata.get("model_provenance_status", "missing")))
    accepted = set(str(item) for item in provenance_policy.get("accepted_statuses", ["passed"]))
    if status not in accepted:
        failures.append(f"model provenance status '{status}' is not accepted")
    statement_type = str(metadata.get("statement_type", "missing"))
    expected_statement = str(provenance_policy.get("statement_type", ""))
    if statement_type != expected_statement:
        failures.append(f"model provenance statement type '{statement_type}' != '{expected_statement}'")
    predicate_type = str(metadata.get("predicate_type", "missing"))
    expected_predicate = str(provenance_policy.get("predicate_type", ""))
    if predicate_type != expected_predicate:
        failures.append(f"model provenance predicate type '{predicate_type}' != '{expected_predicate}'")
    signature_mode = str(metadata.get("signature_mode", "missing"))
    accepted_modes = set(str(item) for item in provenance_policy.get("accepted_signature_modes", []))
    if signature_mode not in accepted_modes:
        failures.append(f"model provenance signature mode '{signature_mode}' is not accepted")
    if str(metadata.get("signer_identity", "")).strip() == "":
        failures.append("model provenance signer identity is missing")
    if not _metadata_bool(metadata.get("verified", False)):
        failures.append("model provenance verification did not pass")
    if failures:
        return GateResult(False, "; ".join(failures))
    return GateResult(True, "model provenance gate passed")


def _check_model_artifacts(candidate: ModelCandidate, policy: dict[str, Any]) -> GateResult:
    artifact_policy = policy.get("model_artifacts", {})
    required_workloads = set(artifact_policy.get("required_for_workloads", []))
    if candidate.workload not in required_workloads:
        return GateResult(True, "model artifact scan not required for workload")
    required_artifact = str(artifact_policy.get("required_artifact", "model_artifact_scan"))
    failures: list[str] = []
    if not candidate.artifacts.get(required_artifact):
        failures.append(f"missing required model artifact scan: {required_artifact}")
    metadata = candidate.metadata.get("model_artifacts", {})
    if not isinstance(metadata, dict):
        metadata = {}
    expected_policy = str(artifact_policy.get("serialization_policy", "safetensors_only"))
    observed_policy = str(metadata.get("serialization_policy", candidate.metadata.get("model_artifact_policy", "missing")))
    if observed_policy != expected_policy:
        failures.append(f"model artifact policy '{observed_policy}' != '{expected_policy}'")
    scan_status = str(metadata.get("scan_status", candidate.metadata.get("model_artifact_scan_status", "missing")))
    if scan_status != "passed":
        failures.append(f"model artifact scan status '{scan_status}' is not passed")
    unsafe_files = int(metadata.get("unsafe_file_count", candidate.metadata.get("model_artifact_unsafe_file_count", 0)) or 0)
    max_unsafe = int(artifact_policy.get("max_unsafe_files", 0))
    if unsafe_files > max_unsafe:
        failures.append(f"unsafe model artifact files {unsafe_files} > {max_unsafe}")
    safetensors_files = int(metadata.get("safetensors_files", candidate.metadata.get("model_artifact_safetensors_files", 0)) or 0)
    min_safetensors = int(artifact_policy.get("min_safetensors_files", 1))
    if safetensors_files < min_safetensors:
        failures.append(f"safetensors files {safetensors_files} < {min_safetensors}")
    rejected_extensions = metadata.get("rejected_extensions", candidate.metadata.get("model_artifact_rejected_extensions", []))
    if rejected_extensions:
        failures.append("rejected model artifact extensions: " + ", ".join(str(item) for item in rejected_extensions))
    if failures:
        return GateResult(False, "; ".join(failures))
    return GateResult(True, "model artifact scan passed")


def _check_metric_gates(candidate: ModelCandidate, policy: dict[str, Any]) -> GateResult:
    gates = policy["metric_gates"].get(candidate.workload, {})
    failures: list[str] = []
    for metric_name, bounds in gates.items():
        if metric_name not in candidate.metrics:
            failures.append(f"missing metric '{metric_name}'")
            continue
        value = candidate.metrics[metric_name]
        if "min" in bounds and value < float(bounds["min"]):
            failures.append(f"{metric_name} {value} < {bounds['min']}")
        if "max" in bounds and value > float(bounds["max"]):
            failures.append(f"{metric_name} {value} > {bounds['max']}")
    if failures:
        return GateResult(False, "; ".join(failures))
    return GateResult(True, "metric gates passed")


def _collect_warnings(candidate: ModelCandidate) -> list[str]:
    warnings: list[str] = []
    if not candidate.metadata.get("code_version"):
        warnings.append("code_version metadata is missing")
    if not candidate.metadata.get("dataset_version"):
        warnings.append("dataset_version metadata is missing")
    if not candidate.metadata.get("pipeline_run_id"):
        warnings.append("pipeline_run_id metadata is missing")
    return warnings


def _metadata_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "passed"}
