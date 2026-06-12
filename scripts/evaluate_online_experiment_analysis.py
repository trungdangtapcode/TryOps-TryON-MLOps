#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_eval_stats import bootstrap_ci_preferred  # noqa: E402
from tryops.native_experiment_stats import analyze_with_native_experiment_stats  # noqa: E402


HOLDBACK = {
    "name": "champion_holdback",
    "impressions": 1000.0,
    "rewards": 820.0,
}

VARIANTS = [
    {
        "name": "champion",
        "impressions": 950.0,
        "rewards": 786.0,
    },
    {
        "name": "challenger",
        "impressions": 800.0,
        "rewards": 760.0,
    },
]

BLOCK_LEVEL_DELTAS = [
    0.10,
    0.11,
    0.13,
    0.12,
    0.14,
    0.09,
    0.16,
    0.13,
    0.15,
    0.12,
    0.11,
    0.14,
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze online experiment outcomes.")
    parser.add_argument("--native-cli", type=Path, default=Path("artifacts/native/tryops_experiment_stats_cli"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/experiments/online_experiment_analysis_report.json"))
    args = parser.parse_args()

    native_stats = analyze_with_native_experiment_stats(
        holdback=HOLDBACK,
        variants=VARIANTS,
        experiment_id="tryops-llm-answer-quality",
        confidence=0.95,
        alpha=0.05,
        beta=0.20,
        min_detectable_effect=0.05,
        min_sample_size=100.0,
        cli_path=args.native_cli,
    )
    bootstrap_ci = bootstrap_ci_preferred(BLOCK_LEVEL_DELTAS, n_resamples=2000, confidence=0.95, seed=37)
    challenger = _variant(native_stats, "challenger")
    champion = _variant(native_stats, "champion")
    checks = {
        "native_stats_available": bool(native_stats.get("available")) and native_stats.get("source") == "native_cpp_cli",
        "theme_n_bootstrap_native": bootstrap_ci.get("engine") == "native",
        "holdback_group_present": native_stats["holdback"]["name"] == "champion_holdback",
        "challenger_ci_excludes_zero": challenger["uplift_ci"]["excludes_zero"],
        "challenger_sequential_early_stop": challenger["sequential"]["early_stop"]
        and challenger["sequential"]["verdict"] == "accept_variant",
        "champion_not_better_than_challenger": champion["uplift_absolute"] < challenger["uplift_absolute"],
    }
    report = {
        "schema_version": "tryops.online_experiment_analysis_report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "experiment_id": native_stats["experiment_id"],
        "native_cli": str(args.native_cli),
        "holdback": HOLDBACK,
        "variant_inputs": VARIANTS,
        "native_experiment_stats": native_stats,
        "theme_n_bootstrap_delta_ci": bootstrap_ci,
        "method_notes": [
            "Sequential decision uses Wald-style SPRT over aggregate Bernoulli rewards.",
            "Uplift CI uses the Agresti-Caffo adjusted difference of proportions.",
            "Theme-N bootstrap CI is computed over deterministic block-level uplift samples.",
        ],
        "checks": checks,
        "passed": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": checks}, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


def _variant(stats: dict[str, object], name: str) -> dict[str, object]:
    for variant in stats["variants"]:  # type: ignore[index]
        if variant["name"] == name:
            return variant
    raise KeyError(name)


if __name__ == "__main__":
    raise SystemExit(main())
