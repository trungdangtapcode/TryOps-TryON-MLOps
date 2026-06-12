from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REQUIRED_NIST_FUNCTIONS = {"GOVERN", "MAP", "MEASURE", "MANAGE"}
REQUIRED_OWASP_2025_IDS = {
    "LLM01:2025",
    "LLM02:2025",
    "LLM03:2025",
    "LLM04:2025",
    "LLM05:2025",
    "LLM06:2025",
    "LLM07:2025",
    "LLM08:2025",
    "LLM09:2025",
    "LLM10:2025",
}


def load_governance_controls(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_governance_report(
    *,
    controls: dict[str, Any],
    llm_security_cases: dict[str, Any] | None = None,
) -> dict[str, Any]:
    risk_mappings = list(controls.get("risk_register_mappings", []))
    owasp_mappings = list(controls.get("owasp_llm_top10_2025", []))
    limitations = list(controls.get("responsible_ai_limitations", []))

    nist_functions = _covered_nist_functions(risk_mappings)
    owasp_ids = {str(item.get("id", "")) for item in owasp_mappings}
    security_cases = list((llm_security_cases or {}).get("cases", []))
    security_case_risk_ids = sorted({str(item.get("owasp_id", "")) for item in security_cases if item.get("owasp_id")})

    mapping_checks = {
        "nist": {
            "required_functions": sorted(REQUIRED_NIST_FUNCTIONS),
            "covered_functions": sorted(nist_functions),
            "missing_functions": sorted(REQUIRED_NIST_FUNCTIONS - nist_functions),
            "risk_count": len(risk_mappings),
            "risks_without_controls": _items_missing(risk_mappings, "controls", "risk_id"),
            "risks_without_evidence": _items_missing(risk_mappings, "evidence", "risk_id"),
        },
        "owasp_llm_top10_2025": {
            "required_ids": sorted(REQUIRED_OWASP_2025_IDS),
            "covered_ids": sorted(owasp_ids),
            "missing_ids": sorted(REQUIRED_OWASP_2025_IDS - owasp_ids),
            "risk_count": len(owasp_mappings),
            "risks_without_controls": _items_missing(owasp_mappings, "controls", "id"),
            "risks_without_evidence": _items_missing(owasp_mappings, "evidence", "id"),
            "security_case_owasp_ids": security_case_risk_ids,
        },
        "responsible_ai": {
            "limitation_count": len(limitations),
            "areas": sorted({str(item.get("area", "")) for item in limitations if item.get("area")}),
            "limitations_without_mitigation": _items_missing(limitations, "mitigation", "id"),
        },
    }
    passed = (
        not mapping_checks["nist"]["missing_functions"]
        and not mapping_checks["nist"]["risks_without_controls"]
        and not mapping_checks["nist"]["risks_without_evidence"]
        and not mapping_checks["owasp_llm_top10_2025"]["missing_ids"]
        and not mapping_checks["owasp_llm_top10_2025"]["risks_without_controls"]
        and not mapping_checks["owasp_llm_top10_2025"]["risks_without_evidence"]
        and mapping_checks["responsible_ai"]["limitation_count"] >= 3
        and not mapping_checks["responsible_ai"]["limitations_without_mitigation"]
    )
    return {
        "schema_version": "tryops.governance_report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "sources": controls.get("sources", {}),
        "mapping_checks": mapping_checks,
        "risk_register_mappings": risk_mappings,
        "owasp_llm_top10_2025": owasp_mappings,
        "responsible_ai_limitations": limitations,
        "passed": passed,
    }


def write_governance_report(
    *,
    controls_path: str | Path,
    output_path: str | Path,
    llm_security_cases_path: str | Path | None = None,
) -> dict[str, Any]:
    controls = load_governance_controls(controls_path)
    security_cases = None
    if llm_security_cases_path is not None:
        security_cases = json.loads(Path(llm_security_cases_path).read_text(encoding="utf-8"))
    report = build_governance_report(controls=controls, llm_security_cases=security_cases)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _covered_nist_functions(risk_mappings: list[dict[str, Any]]) -> set[str]:
    covered: set[str] = set()
    for item in risk_mappings:
        for function in item.get("nist_functions", []):
            covered.add(str(function))
    return covered


def _items_missing(items: list[dict[str, Any]], field: str, id_field: str) -> list[str]:
    missing = []
    for item in items:
        value = item.get(field)
        if isinstance(value, list) and value:
            continue
        if isinstance(value, str) and value.strip():
            continue
        missing.append(str(item.get(id_field, "unknown")))
    return sorted(missing)
