from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_DASHBOARDS = {
    "tryops-service-overview": {
        "title": "TryOps Service Overview",
        "required_panels": [
            "Persisted API Requests",
            "API Error Ratio",
            "Observed Workload Latency",
            "Async VTON Queue Depth",
            "Gateway Request Rate",
            "Gateway p95 Latency",
            "Gateway Rejections and Upstream Errors",
        ],
    },
    "tryops-model-quality": {
        "title": "TryOps Model Quality",
        "required_panels": [
            "LLM Completed Requests",
            "VTON Completed Requests",
            "LLM Observed Latency",
            "VTON Latency",
        ],
    },
    "tryops-cost-capacity": {
        "title": "TryOps Cost and Capacity",
        "required_panels": [
            "Estimated Daily Request Cost",
            "Quota Utilization",
            "Observed Energy Total",
            "Estimated CO2e From Energy",
            "Cost vs Observed Energy",
            "Cost and Capacity Evidence Map",
        ],
    },
    "tryops-guardrails": {
        "title": "TryOps LLM Guardrails",
        "required_panels": [
            "Blocked Requests by OWASP Risk",
            "Guardrail Actions by Risk",
            "Guardrail Evidence Map",
        ],
    },
    "tryops-observability-drilldown": {
        "title": "TryOps Observability Drilldown",
        "required_panels": [
            "Scrape Target Health",
            "OTel Collector Throughput",
            "Loki and Tempo Health",
            "FASHN VTON Service Logs",
            "Async Job Lifecycle Logs",
            "Error Logs",
            "Trace and Log Drilldown",
        ],
    },
}


def validate_dashboard_directory(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    dashboards = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(root_path.glob("*.json"))]
    checks = []
    seen_uids: set[str] = set()
    for dashboard in dashboards:
        uid = str(dashboard.get("uid", ""))
        title = str(dashboard.get("title", ""))
        panels = dashboard.get("panels", [])
        panel_titles = {str(panel.get("title", "")) for panel in panels if isinstance(panel, dict)}
        required = REQUIRED_DASHBOARDS.get(uid, {})
        missing_panels = [panel for panel in required.get("required_panels", []) if panel not in panel_titles]
        targets = _targets(dashboard)
        datasource_uids = {target.get("datasource_uid") for target in targets if target.get("datasource_uid")}
        check = {
            "uid": uid,
            "title": title,
            "panel_count": len(panels) if isinstance(panels, list) else 0,
            "target_count": len(targets),
            "datasource_uids": sorted(datasource_uids),
            "missing_required_panels": missing_panels,
            "valid": bool(uid)
            and uid not in seen_uids
            and title == required.get("title")
            and not missing_panels
            and len(panels) >= len(required.get("required_panels", [])),
        }
        seen_uids.add(uid)
        checks.append(check)

    expected_uids = set(REQUIRED_DASHBOARDS)
    found_uids = {check["uid"] for check in checks}
    missing_dashboards = sorted(expected_uids - found_uids)
    return {
        "schema_version": "tryops.dashboard_validation.v1",
        "dashboard_count": len(dashboards),
        "required_dashboard_count": len(REQUIRED_DASHBOARDS),
        "missing_dashboards": missing_dashboards,
        "checks": checks,
        "passed": not missing_dashboards and all(check["valid"] for check in checks),
    }


def _targets(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    targets = []
    for panel in dashboard.get("panels", []):
        if not isinstance(panel, dict):
            continue
        datasource = panel.get("datasource", {})
        datasource_uid = datasource.get("uid") if isinstance(datasource, dict) else None
        for target in panel.get("targets", []):
            if isinstance(target, dict):
                targets.append(
                    {
                        "panel": panel.get("title"),
                        "expr": target.get("expr"),
                        "datasource_uid": datasource_uid,
                    }
                )
    return targets
