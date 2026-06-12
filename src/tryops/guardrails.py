from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tryops.native_safety import evaluate_with_native_safety


GUARDRAIL_VERDICT_SCHEMA = "tryops.guardrail_verdict.v1"
GUARDRAIL_REPORT_SCHEMA = "tryops.guardrail_report.v1"
NATIVE_GUARDRAIL_SCHEMA = "tryops.native_guardrail.v1"
DEFAULT_NATIVE_GUARDRAIL_CLI = Path("artifacts/native/tryops_guardrail_cli")


PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"\b(?:sk-[A-Za-z0-9]{8,}|AKIA[A-Z0-9]{8,})\b")),
    ("secret_assignment", re.compile(r"(?i)\b(?:api[_-]?key|password|secret|token)\s*[=:]\s*\S+")),
    ("email", re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b")),
    ("ssn", re.compile(r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b")),
    ("phone", re.compile(r"(?i)(?:\+?1[\s.\-]?)?(?:\([0-9]{3}\)|[0-9]{3})[\s.\-]?[0-9]{3}[\s.\-]?[0-9]{4}\b")),
    ("payment_card", re.compile(r"\b(?:[0-9][ -]?){13,19}\b")),
]


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    replacements: list[dict[str, Any]]
    token_map: dict[str, str]

    def public_summary(self) -> dict[str, Any]:
        counts = Counter(str(item["entity_type"]) for item in self.replacements)
        return {
            "redacted": bool(self.replacements),
            "entity_count": len(self.replacements),
            "entity_counts": dict(sorted(counts.items())),
            "tokens": [
                {
                    "entity_type": item["entity_type"],
                    "token": item["token"],
                    "start": item["start"],
                    "end": item["end"],
                }
                for item in self.replacements
            ],
        }


def redact_pii(text: str) -> RedactionResult:
    """Presidio-style deterministic PII masking for offline runtime safety."""

    source = str(text)
    matches: list[tuple[int, int, str, str]] = []
    occupied: set[int] = set()
    for entity_type, pattern in PII_PATTERNS:
        for match in pattern.finditer(source):
            span = set(range(match.start(), match.end()))
            if occupied.intersection(span):
                continue
            occupied.update(span)
            matches.append((match.start(), match.end(), entity_type, match.group(0)))
    matches.sort(key=lambda item: item[0])

    pieces: list[str] = []
    cursor = 0
    counters: Counter[str] = Counter()
    replacements: list[dict[str, Any]] = []
    token_map: dict[str, str] = {}
    for start, end, entity_type, original in matches:
        counters[entity_type] += 1
        token = "{{TRYOPS_PII_" + entity_type.upper() + "_" + str(counters[entity_type]) + "}}"
        pieces.append(source[cursor:start])
        pieces.append(token)
        replacements.append(
            {
                "entity_type": entity_type,
                "token": token,
                "start": start,
                "end": end,
            }
        )
        token_map[token] = original
        cursor = end
    pieces.append(source[cursor:])
    return RedactionResult(redacted_text="".join(pieces), replacements=replacements, token_map=token_map)


def restore_pii_placeholders(text: str, redaction: RedactionResult) -> str:
    restored = str(text)
    for token, original in redaction.token_map.items():
        restored = restored.replace(token, original)
    return restored


def evaluate_ingress_guardrails(
    *,
    prompt: str,
    max_tokens: int,
    structured: bool,
    native_cli: str | Path | None = None,
) -> dict[str, Any]:
    redaction = redact_pii(prompt)
    native = run_native_guardrail(
        prompt=prompt,
        max_tokens=max_tokens,
        structured=structured,
        native_cli=native_cli,
    )
    native_safety = evaluate_with_native_safety(prompt)
    native["content_safety"] = _content_safety_summary(native_safety)
    findings = _dedupe_findings(
        _pii_findings(redaction)
        + _native_findings(native, stage="ingress")
        + _native_safety_findings(native_safety)
    )
    verdict = _build_verdict(
        stage="ingress",
        findings=findings,
        native=native,
        pii=redaction.public_summary(),
    )
    return {
        "prompt_for_generation": redaction.redacted_text,
        "redaction": redaction,
        "verdict": verdict,
    }


def evaluate_egress_guardrails(
    *,
    generation: dict[str, Any],
    redaction: RedactionResult | None = None,
    structured: bool = True,
    native_cli: str | Path | None = None,
) -> dict[str, Any]:
    restored_generation = _restore_generation_placeholders(generation, redaction)
    output_text = str(restored_generation.get("output", {}).get("text", ""))
    native = run_native_guardrail(
        prompt="",
        output_text=output_text,
        max_tokens=int(restored_generation.get("output", {}).get("estimated_tokens", 0) or 0),
        structured=structured,
        structured_answer=restored_generation.get("structured_answer"),
        native_cli=native_cli,
    )
    findings = _dedupe_findings(
        _native_findings(native, stage="egress")
        + validate_structured_output(restored_generation, structured=structured)
    )
    verdict = _build_verdict(
        stage="egress",
        findings=findings,
        native=native,
        pii=(redaction.public_summary() if redaction is not None else {"redacted": False, "entity_count": 0}),
    )
    return {
        "generation": restored_generation,
        "verdict": verdict,
    }


def merge_guardrail_verdicts(*verdicts: dict[str, Any]) -> dict[str, Any]:
    findings = _dedupe_findings([finding for verdict in verdicts for finding in verdict.get("findings", [])])
    native = next((verdict.get("native_engine") for verdict in verdicts if verdict.get("native_engine")), {})
    pii = next((verdict.get("pii") for verdict in verdicts if verdict.get("pii", {}).get("redacted")), {"redacted": False, "entity_count": 0})
    return _build_verdict(stage="runtime", findings=findings, native=native, pii=pii)


def validate_structured_output(generation: dict[str, Any], *, structured: bool) -> list[dict[str, Any]]:
    if not structured:
        return []
    answer = generation.get("structured_answer")
    if not isinstance(answer, dict):
        return [
            _finding(
                check_id="structured_output_schema",
                owasp_id="LLM05:2025",
                risk="improper_output_handling",
                stage="egress",
                action="block",
                severity="high",
                message="structured output is missing or not an object",
            )
        ]
    failures: list[str] = []
    if not isinstance(answer.get("intent"), str) or not str(answer.get("intent", "")).strip():
        failures.append("intent must be a non-empty string")
    points = answer.get("points")
    if "points" in answer and not (
        isinstance(points, list) and all(isinstance(item, str) and item.strip() for item in points)
    ):
        failures.append("points must be a list of non-empty strings")
    unsafe_keys = sorted({"system_prompt", "developer_message", "api_key", "password", "secret"} & set(answer))
    if unsafe_keys:
        failures.append("unsafe structured keys present: " + ", ".join(unsafe_keys))
    if failures:
        return [
            _finding(
                check_id="structured_output_schema",
                owasp_id="LLM05:2025",
                risk="improper_output_handling",
                stage="egress",
                action="block",
                severity="high",
                message="; ".join(failures),
            )
        ]
    return [
        _finding(
            check_id="structured_output_schema",
            owasp_id="LLM05:2025",
            risk="improper_output_handling",
            stage="egress",
            action="allow",
            severity="info",
            message="structured output schema passed",
        )
    ]


def run_native_guardrail(
    *,
    prompt: str,
    output_text: str = "",
    max_tokens: int,
    structured: bool,
    structured_answer: Any = None,
    native_cli: str | Path | None = None,
) -> dict[str, Any]:
    service_url = str(os.environ.get("TRYOPS_GUARDRAIL_URL", "")).strip()
    request = {
        "prompt": str(prompt),
        "output_text": str(output_text),
        "max_tokens": int(max_tokens),
        "structured": bool(structured),
        "structured_answer": structured_answer if isinstance(structured_answer, dict) else {},
    }
    if service_url:
        service_result = _post_native_guardrail_service(service_url, request)
        if service_result is not None:
            return service_result

    cli = Path(
        str(
            native_cli
            or os.environ.get("TRYOPS_NATIVE_GUARDRAIL_CLI")
            or DEFAULT_NATIVE_GUARDRAIL_CLI
        )
    )
    if cli.exists() and os.access(cli, os.X_OK):
        try:
            completed = subprocess.run(
                [str(cli)],
                input=json.dumps(request),
                text=True,
                capture_output=True,
                check=True,
                timeout=2.0,
            )
            payload = json.loads(completed.stdout)
            payload["available"] = payload.get("schema_version") == NATIVE_GUARDRAIL_SCHEMA
            payload["source"] = "native_go_cli"
            return payload
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TimeoutError) as exc:
            fallback = _python_native_equivalent(request)
            fallback["available"] = False
            fallback["source"] = "python_fallback_after_native_error"
            fallback["native_error"] = str(exc)
            return fallback
    fallback = _python_native_equivalent(request)
    fallback["available"] = False
    fallback["source"] = "python_deterministic_fallback"
    return fallback


def _post_native_guardrail_service(service_url: str, request: dict[str, Any]) -> dict[str, Any] | None:
    body = json.dumps(request).encode("utf-8")
    http_request = urllib.request.Request(
        service_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None
    payload["available"] = payload.get("schema_version") == NATIVE_GUARDRAIL_SCHEMA
    payload["source"] = "native_go_sidecar"
    return payload


def build_guardrail_report(results: list[dict[str, Any]], *, source_set: str) -> dict[str, Any]:
    risk_counts: dict[str, Counter[str]] = {}
    blocked_cases = 0
    for result in results:
        verdict = result["verdict"]
        if verdict["blocked"]:
            blocked_cases += 1
        for risk_id in verdict["risk_ids"]:
            risk_counts.setdefault(risk_id, Counter())
            risk_counts[risk_id]["blocked" if verdict["blocked"] else "passed"] += 1
        if not verdict["risk_ids"]:
            risk_counts.setdefault("none", Counter())
            risk_counts["none"]["passed"] += 1

    by_risk = [
        {
            "owasp_id": risk_id,
            "blocked": counts.get("blocked", 0),
            "passed": counts.get("passed", 0),
            "total": sum(counts.values()),
        }
        for risk_id, counts in sorted(risk_counts.items())
    ]
    native_available = any(result["verdict"].get("native_engine", {}).get("available") for result in results)
    failed_cases = [result for result in results if not result["expected_passed"]]
    passed = not failed_cases
    blocked_risk_ids = sorted(
        {
            risk_id
            for result in results
            if result["verdict"]["blocked"]
            for risk_id in result["verdict"]["risk_ids"]
        }
    )
    return {
        "schema_version": GUARDRAIL_REPORT_SCHEMA,
        "source_set": source_set,
        "case_count": len(results),
        "blocked_cases": blocked_cases,
        "passed_cases": len(results) - blocked_cases,
        "failed_cases": len(failed_cases),
        "passed": passed,
        "promotion_gate_input": {
            "status": "passed" if passed else "failed",
            "failed_cases": len(failed_cases),
            "blocked_risk_ids": [],
            "observed_blocked_risk_ids": blocked_risk_ids,
        },
        "native_engine_available": native_available,
        "by_owasp_risk": by_risk,
        "results": results,
    }


def _restore_generation_placeholders(generation: dict[str, Any], redaction: RedactionResult | None) -> dict[str, Any]:
    if redaction is None or not redaction.token_map:
        return generation
    restored = json.loads(json.dumps(generation))
    output = restored.get("output")
    if isinstance(output, dict) and isinstance(output.get("text"), str):
        output["text"] = restore_pii_placeholders(output["text"], redaction)
    answer = restored.get("structured_answer")
    if isinstance(answer, dict):
        for key, value in list(answer.items()):
            if isinstance(value, str):
                answer[key] = restore_pii_placeholders(value, redaction)
            elif isinstance(value, list):
                answer[key] = [restore_pii_placeholders(item, redaction) if isinstance(item, str) else item for item in value]
    return restored


def _pii_findings(redaction: RedactionResult) -> list[dict[str, Any]]:
    if not redaction.replacements:
        return []
    return [
        _finding(
            check_id="pii_ingress",
            owasp_id="LLM02:2025",
            risk="sensitive_information_disclosure",
            stage="ingress",
            action="redact",
            severity="medium",
            message="PII-like input detected and replaced with scoped placeholders",
        )
    ]


def _native_findings(native: dict[str, Any], *, stage: str) -> list[dict[str, Any]]:
    findings = []
    for item in native.get("findings", []):
        if not isinstance(item, dict):
            continue
        item_stage = str(item.get("stage", stage))
        if item_stage != stage:
            continue
        findings.append(
            _finding(
                check_id=str(item.get("check_id", "native_guardrail")),
                owasp_id=str(item.get("owasp_id", "unknown")),
                risk=str(item.get("risk", "unknown")),
                stage=item_stage,
                action=str(item.get("action", "review")),
                severity=str(item.get("severity", "medium")),
                message=str(item.get("message", "native guardrail finding")),
            )
        )
    return findings


def _native_safety_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    verdict = str(report.get("verdict", "allow"))
    if verdict == "allow":
        return []
    action = "block" if verdict == "block" else "review"
    severity = "high" if verdict == "block" else "medium"
    categories = report.get("categories", {})
    if not isinstance(categories, dict):
        categories = {}
    if int(report.get("exfiltration_hits", 0) or 0) > 0:
        owasp_id = "LLM07:2025"
        risk = "system_prompt_leakage"
    elif int(report.get("injection_hits", 0) or 0) > 0:
        owasp_id = "LLM01:2025"
        risk = "prompt_injection"
    else:
        owasp_id = "LLM04:2025"
        risk = "unsafe_content"
    verb = "blocked" if verdict == "block" else "flagged"
    message = (
        "native content-safety gate "
        f"{verb} prompt with risk_score={float(report.get('risk_score', 0.0) or 0.0):.4f} "
        f"categories={dict(sorted(categories.items()))}"
    )
    return [
        _finding(
            check_id="native_content_safety",
            owasp_id=owasp_id,
            risk=risk,
            stage="ingress",
            action=action,
            severity=severity,
            message=message,
        )
    ]


def _content_safety_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "tryops.native_safety.report.v1",
        "available": report.get("engine") == "native",
        "source": report.get("engine", "unknown"),
        "verdict": report.get("verdict", "allow"),
        "risk_score": report.get("risk_score", 0.0),
        "injection_hits": report.get("injection_hits", 0),
        "exfiltration_hits": report.get("exfiltration_hits", 0),
        "toxicity_hits": report.get("toxicity_hits", 0),
        "categories": report.get("categories", {}),
    }


def _build_verdict(
    *,
    stage: str,
    findings: list[dict[str, Any]],
    native: dict[str, Any],
    pii: dict[str, Any],
) -> dict[str, Any]:
    blocked = any(item["action"] == "block" for item in findings)
    risk_ids = sorted({item["owasp_id"] for item in findings if item["owasp_id"] != "unknown"})
    actions = Counter(str(item["action"]) for item in findings)
    return {
        "schema_version": GUARDRAIL_VERDICT_SCHEMA,
        "stage": stage,
        "status": "blocked" if blocked else "passed",
        "blocked": blocked,
        "risk_ids": risk_ids,
        "action_counts": dict(sorted(actions.items())),
        "findings": findings,
        "pii": pii,
        "native_engine": {
            "schema_version": native.get("schema_version", NATIVE_GUARDRAIL_SCHEMA),
            "available": bool(native.get("available", False)),
            "source": native.get("source", "unknown"),
            "engine": native.get("engine", {"name": "tryops-python-guardrail", "language": "python", "version": "0.1.0"}),
            "content_safety": native.get("content_safety", {}),
        },
        "control_map": _control_map(findings),
    }


def _control_map(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    controls = {
        ("LLM01:2025", "prompt_injection"): "input classifier blocks instruction-override attempts",
        ("LLM02:2025", "sensitive_information_disclosure"): "PII redaction and secret-disclosure blocks",
        ("LLM05:2025", "improper_output_handling"): "structured output schema validator",
        ("LLM06:2025", "excessive_agency"): "no external-tool agency boundary",
        ("LLM07:2025", "system_prompt_leakage"): "system/developer prompt leakage block",
        ("LLM10:2025", "unbounded_consumption"): "unbounded-output and max-token guard",
        ("LLM04:2025", "unsafe_content"): "native content-safety gate flags abusive or toxic prompts",
    }
    mapped = []
    for item in findings:
        key = (item["owasp_id"], item["risk"])
        mapped.append(
            {
                "owasp_id": item["owasp_id"],
                "risk": item["risk"],
                "control": controls.get(key, "deterministic runtime guardrail"),
            }
        )
    return [json.loads(item) for item in sorted({json.dumps(item, sort_keys=True) for item in mapped})]


def _finding(
    *,
    check_id: str,
    owasp_id: str,
    risk: str,
    stage: str,
    action: str,
    severity: str,
    message: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "owasp_id": owasp_id,
        "risk": risk,
        "stage": stage,
        "action": action,
        "severity": severity,
        "message": message,
    }


def _dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in findings:
        key = (str(item.get("check_id")), str(item.get("owasp_id")), str(item.get("stage")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _python_native_equivalent(request: dict[str, Any]) -> dict[str, Any]:
    prompt = str(request.get("prompt", ""))
    output_text = str(request.get("output_text", ""))
    max_tokens = int(request.get("max_tokens", 0) or 0)
    lower_prompt = prompt.lower()
    lower_output = output_text.lower()
    findings: list[dict[str, Any]] = []

    if redact_pii(prompt).replacements:
        findings.append(_native_style_finding("pii_ingress", "LLM02:2025", "sensitive_information_disclosure", "ingress", "redact", "medium", "PII-like input detected; redact before generation"))
    if any(term in lower_prompt for term in ["ignore previous", "ignore all policy", "bypass policy", "jailbreak", "dan mode", "developer mode", "override instructions"]):
        findings.append(_native_style_finding("prompt_injection", "LLM01:2025", "prompt_injection", "ingress", "block", "high", "Prompt attempts to override application instructions"))
    if any(term in lower_prompt for term in ["system prompt", "developer message", "hidden instruction", "internal policy", "chain of thought"]) and any(term in lower_prompt for term in ["print", "show", "reveal", "dump", "expose"]):
        findings.append(_native_style_finding("system_prompt_leakage", "LLM07:2025", "system_prompt_leakage", "ingress", "block", "high", "Prompt requests hidden system or developer instructions"))
    if any(term in lower_prompt for term in ["api keys", "api key", "password", "secret", "hidden credential", "deployment environment", "environment variables"]) and any(term in lower_prompt for term in ["show", "print", "reveal", "dump", "exfiltrate"]):
        findings.append(_native_style_finding("secret_disclosure_request", "LLM02:2025", "sensitive_information_disclosure", "ingress", "block", "high", "Prompt requests secrets or deployment credentials"))
    if re.search(r"(?i)\b(repeat|loop|continue|generate|write)\b.{0,80}\b(forever|without stopping|infinite|until cancelled)\b", prompt) or (max_tokens > 1024 and any(term in lower_prompt for term in ["longest possible", "maximum tokens", "as much as possible"])):
        findings.append(_native_style_finding("unbounded_consumption", "LLM10:2025", "unbounded_consumption", "ingress", "block", "medium", "Prompt attempts to consume unbounded output or compute"))
    if any(term in lower_prompt for term in ["delete database", "run shell", "execute command", "send email to all", "make a purchase"]):
        findings.append(_native_style_finding("excessive_agency", "LLM06:2025", "excessive_agency", "ingress", "block", "high", "Prompt requests unsafe autonomous action outside the LLM boundary"))
    if output_text and re.search(r"(?i)\b(?:sk-[A-Za-z0-9]{8,}|AKIA[A-Z0-9]{8,}|(?:api[_-]?key|password|secret|token)\s*[=:]\s*\S+)", output_text):
        findings.append(_native_style_finding("credential_output", "LLM02:2025", "sensitive_information_disclosure", "egress", "block", "critical", "Generated output contains credential-like material"))
    if output_text and any(term in lower_output for term in ["begin_system_prompt", "system_prompt=", "developer_message="]):
        findings.append(_native_style_finding("system_prompt_output", "LLM07:2025", "system_prompt_leakage", "egress", "block", "critical", "Generated output resembles hidden prompt leakage"))

    blocked = any(item["action"] == "block" for item in findings)
    return {
        "schema_version": NATIVE_GUARDRAIL_SCHEMA,
        "engine": {"name": "tryops-python-guardrail", "language": "python", "version": "0.1.0"},
        "status": "blocked" if blocked else "passed",
        "blocked": blocked,
        "risk_ids": sorted({item["owasp_id"] for item in findings}),
        "findings": findings,
    }


def _native_style_finding(
    check_id: str,
    owasp_id: str,
    risk: str,
    stage: str,
    action: str,
    severity: str,
    message: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "owasp_id": owasp_id,
        "risk": risk,
        "stage": stage,
        "action": action,
        "severity": severity,
        "message": message,
    }
