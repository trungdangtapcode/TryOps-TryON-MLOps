from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.chaos import DEFAULT_CHAOS_SCENARIOS, run_chaos_drill  # noqa: E402
from tryops.deployment import build_deployment_package  # noqa: E402
from tryops.native_chaos import evaluate_with_native_chaos  # noqa: E402
from tryops.pipelines.promotion import run_local_promotion_pipeline  # noqa: E402

NATIVE_BURN_CLI = ROOT / "artifacts/native/tryops_burn_rate_cli"


class ChaosTests(unittest.TestCase):
    def test_native_chaos_fallback_covers_required_fault_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = evaluate_with_native_chaos(
                DEFAULT_CHAOS_SCENARIOS,
                cli_path=Path(temp_dir) / "missing-native-chaos",
            )

        self.assertFalse(result["available"])
        self.assertEqual(result["scenario_count"], 4)
        self.assertEqual(
            {scenario["type"] for scenario in result["scenarios"]},
            {"gpu_oom", "slow_decode", "corrupted_weights", "poisoned_candidate"},
        )
        self.assertTrue(all(scenario["rollback_required"] for scenario in result["scenarios"]))

    @unittest.skipUnless(NATIVE_BURN_CLI.exists(), "native burn-rate CLI not built")
    def test_chaos_drill_triggers_auto_rollback_on_page_burn_rate(self) -> None:
        candidate = json.loads((ROOT / "samples/candidates/vton_candidate_good.json").read_text())
        manifest = json.loads((ROOT / "samples/data/demo_manifest.json").read_text())
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            promotion = run_local_promotion_pipeline(
                candidate_payload=candidate,
                dataset_manifest=manifest,
                target_stage="champion",
                output_dir=root / "reports",
            )
            package = build_deployment_package(
                promotion_run_dir=promotion["run_dir"],
                output_dir=root / "deployments",
                profile="production-demo",
                previous_candidate_id="previous-model",
            )
            report = run_chaos_drill(
                slo_config=_slo_config(),
                package_id=package["manifest"]["package_id"],
                packages_dir=root / "deployments",
                native_chaos_cli=root / "missing-chaos",
                native_burn_cli=NATIVE_BURN_CLI,
            )

            rollback_state = json.loads((root / "deployments" / "rollback_state.json").read_text())

        self.assertTrue(report["auto_rollback"]["triggered"])
        self.assertGreaterEqual(report["auto_rollback"]["trigger_count"], 1)
        self.assertEqual(report["auto_rollback"]["record"]["restored_candidate_id"], "previous-model")
        self.assertIn("triggered_by", rollback_state["latest_rollback"])


def _slo_config() -> dict[str, object]:
    return {
        "workloads": {
            "llm": {"error_budget_ratio": 0.01},
            "vton": {"error_budget_ratio": 0.01},
            "control_plane": {"error_budget_ratio": 0.005},
        },
        "default_windows": [
            {
                "name": "page_fast",
                "long_window": "1h",
                "short_window": "5m",
                "burn_rate_threshold": 14.4,
                "severity": "page",
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
