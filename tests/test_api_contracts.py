from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.api_contracts import (  # noqa: E402
    request_id_from_payload,
    structured_error,
    validate_llm_payload,
    validate_vton_payload,
)
from tryops.routing import build_routing_decision, resolve_model_alias  # noqa: E402
from tryops.simple_image import solid_rgb, write_png_rgb  # noqa: E402


class ApiContractTests(unittest.TestCase):
    def test_llm_validation_rejects_missing_prompt_and_bad_token_limit(self) -> None:
        clean, errors = validate_llm_payload({"model_alias": "baseline", "max_tokens": 99999})

        self.assertEqual(clean["model_alias"], "baseline")
        self.assertEqual(clean["user_id"], "anonymous")
        self.assertEqual(clean["quota_plan"], "free")
        self.assertEqual(clean["timeout_ms"], 30000)
        self.assertIn("prompt", {error["field"] for error in errors})
        self.assertIn("max_tokens", {error["field"] for error in errors})

    def test_llm_validation_accepts_quota_and_fallback_fields(self) -> None:
        clean, errors = validate_llm_payload(
            {
                "prompt": "Explain TryOps.",
                "model_alias": "champion",
                "user_id": "customer-123",
                "quota_plan": "team",
                "fallback_enabled": True,
                "optimized_available": False,
                "timeout_ms": 1000,
            }
        )

        self.assertEqual(errors, [])
        self.assertEqual(clean["user_id"], "customer-123")
        self.assertEqual(clean["quota_plan"], "team")
        self.assertTrue(clean["fallback_enabled"])
        self.assertFalse(clean["optimized_available"])
        self.assertEqual(clean["timeout_ms"], 1000)

    def test_vton_validation_checks_alias_paths_and_file_size_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person = root / "person.png"
            garment = root / "garment.png"
            output = root / "output.png"
            write_png_rgb(person, solid_rgb(16, 16, (10, 20, 30)))
            write_png_rgb(garment, solid_rgb(16, 16, (200, 20, 30)))

            clean, errors = validate_vton_payload(
                {
                    "person_image_path": str(person),
                    "garment_image_path": str(garment),
                    "output_image_path": str(output),
                    "model_alias": "champion",
                }
            )

            self.assertEqual(errors, [])
            self.assertEqual(clean["model_alias"], "champion")
            self.assertEqual(clean["user_id"], "anonymous")
            self.assertEqual(clean["quota_plan"], "free")
            self.assertEqual(clean["timeout_ms"], 30000)
            self.assertEqual(clean["output_image_path"], str(output))

    def test_structured_error_and_request_id_contract(self) -> None:
        request_id = request_id_from_payload({"request_id": "demo-request"})
        response = structured_error(
            request_id=request_id,
            code="invalid_request",
            message="validation failed",
            details=[{"field": "prompt", "message": "missing"}],
            workload="llm",
        )

        self.assertEqual(response["api_version"], "v1")
        self.assertEqual(response["request_id"], "demo-request")
        self.assertEqual(response["error"]["code"], "invalid_request")
        self.assertEqual(response["workload"], "llm")

    def test_safe_alias_and_canary_routing(self) -> None:
        route = resolve_model_alias("llm", "champion")
        self.assertEqual(route["adapter"], "tryops-rule-baseline")

        decision = build_routing_decision(
            workload="llm",
            request_id="request-canary",
            requested_alias="champion",
            routing_mode="canary",
            canary_percent=100.0,
            shadow=True,
        )

        self.assertEqual(decision["primary_alias"], "challenger")
        self.assertEqual(decision["shadow_alias"], "champion")

    def test_llm_fallback_routing_switches_unavailable_optimized_alias_to_baseline(self) -> None:
        decision = build_routing_decision(
            workload="llm",
            request_id="request-fallback",
            requested_alias="challenger",
            fallback_enabled=True,
            route_health={"baseline": "ready", "challenger": "unavailable"},
        )

        self.assertEqual(decision["primary_alias"], "baseline")
        self.assertEqual(decision["pre_fallback_alias"], "challenger")
        self.assertTrue(decision["fallback"]["applied"])


if __name__ == "__main__":
    unittest.main()
