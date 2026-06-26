from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.dashboards import validate_dashboard_directory  # noqa: E402


class DashboardTests(unittest.TestCase):
    def test_grafana_dashboard_directory_has_required_dashboards(self) -> None:
        report = validate_dashboard_directory(ROOT / "infra/grafana/dashboards")

        self.assertTrue(report["passed"])
        self.assertEqual(report["dashboard_count"], 5)
        self.assertEqual(report["missing_dashboards"], [])
        datasource_sets = [set(check["datasource_uids"]) for check in report["checks"]]
        self.assertTrue(any("prometheus" in datasource_uids for datasource_uids in datasource_sets))
        self.assertTrue(any("loki" in datasource_uids for datasource_uids in datasource_sets))

    def test_grafana_provider_points_to_mounted_dashboard_directory(self) -> None:
        provider = (ROOT / "infra/grafana/provisioning/dashboards/tryops.yml").read_text(encoding="utf-8")
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("path: /var/lib/grafana/dashboards", provider)
        self.assertIn("./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro", compose)

    def test_prometheus_datasource_has_stable_uid(self) -> None:
        datasource = (ROOT / "infra/grafana/provisioning/datasources/prometheus.yml").read_text(encoding="utf-8")

        self.assertIn("uid: prometheus", datasource)
        self.assertIn("url: http://prometheus:9090", datasource)

    def test_observability_long_running_services_use_init(self) -> None:
        compose = (ROOT / "docker-compose.observability.yml").read_text(encoding="utf-8")

        for service_name in ("loki", "tempo", "tryops-otel-bridge"):
            match = re.search(rf"^  {service_name}:\n(?P<body>.*?)(?=^  \S|\Z)", compose, re.M | re.S)
            self.assertIsNotNone(match)
            service_block = match.group("body") if match else ""
            self.assertIn("init: true", service_block)

    def test_cost_dashboard_has_energy_and_cost_correlation_panels(self) -> None:
        dashboard = (ROOT / "infra/grafana/dashboards/tryops-cost-capacity.json").read_text(encoding="utf-8")

        self.assertIn("Observed Energy Total", dashboard)
        self.assertIn("Estimated CO2e From Energy", dashboard)
        self.assertIn("Cost vs Observed Energy", dashboard)
        self.assertIn("tryops_energy_wh_total", dashboard)
        self.assertIn("tryops_request_cost_usd_per_1k_tokens", dashboard)

    def test_observability_dashboard_has_loki_log_panels(self) -> None:
        dashboard = (ROOT / "infra/grafana/dashboards/tryops-observability-drilldown.json").read_text(
            encoding="utf-8"
        )
        datasource = (ROOT / "infra/grafana/provisioning/datasources/observability.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("uid: loki", datasource)
        self.assertIn("uid: tempo", datasource)
        self.assertIn("TRYOPS_REAL_VTON_URL Logs", dashboard)
        self.assertIn("FASHN VTON Service Logs", dashboard)
        self.assertIn("Async Job Lifecycle Logs", dashboard)
        self.assertIn("Error Logs", dashboard)
        self.assertIn("tryops.real_vton_url", dashboard)
        self.assertIn("tryops.fashn_router", dashboard)
        self.assertIn("tryops.fashn_vton", dashboard)
        self.assertIn("tryops.job.status", dashboard)

    def test_native_guardrail_sidecar_is_wired_to_api_and_prometheus(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        prometheus = (ROOT / "infra/prometheus/prometheus.yml").read_text(encoding="utf-8")

        self.assertIn("guardrail:", compose)
        self.assertIn("Dockerfile.guardrail", compose)
        self.assertIn("TRYOPS_GUARDRAIL_URL: http://guardrail:18083/v1/guardrails/evaluate", compose)
        self.assertIn("tryops-guardrail", prometheus)
        self.assertIn('targets: ["guardrail:18083"]', prometheus)

    def test_native_gateway_metrics_are_scraped_and_dashboarded(self) -> None:
        prometheus = (ROOT / "infra/prometheus/prometheus.yml").read_text(encoding="utf-8")
        dashboard = (ROOT / "infra/grafana/dashboards/tryops-service-overview.json").read_text(encoding="utf-8")

        self.assertIn("tryops-gateway", prometheus)
        self.assertIn('targets: ["gateway:8081"]', prometheus)
        self.assertIn("Gateway Request Rate", dashboard)
        self.assertIn("Gateway p95 Latency", dashboard)
        self.assertIn("Gateway Rejections and Upstream Errors", dashboard)
        self.assertIn("tryops_gateway_requests_total", dashboard)
        self.assertIn("tryops_gateway_request_latency_ms_bucket", dashboard)
        self.assertIn("tryops_gateway_rate_limited_total", dashboard)


if __name__ == "__main__":
    unittest.main()
