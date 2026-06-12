#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_vton_eval import evaluate_vton_with_native  # noqa: E402


SECTION_TITLE = "## Advanced VTON Evaluation and Fairness"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate advanced VTON quality and fairness with the native C++ engine.")
    parser.add_argument("--comparison", type=Path, default=Path("artifacts/eval/vton_comparison/comparison.json"))
    parser.add_argument("--study", type=Path, default=Path("samples/eval/vton_preference_study.json"))
    parser.add_argument("--native-cli", type=Path, default=Path("artifacts/native/tryops_vton_eval_cli"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/vton_advanced/vton_advanced_eval_report.json"))
    parser.add_argument(
        "--model-card",
        type=Path,
        default=Path("reports/generated/vton-catvton-2026-06-11-001/model_card.md"),
    )
    args = parser.parse_args()

    comparison = _read_json(args.comparison)
    study = _read_json(args.study)
    preferences = list(study.get("preferences", []))
    fairness_slices = list(study.get("fairness_slices", []))
    person_image = Path(str(comparison["person_image_path"]))
    garment_image = Path(str(comparison["garment_image_path"]))

    runs = []
    for run in comparison["runs"]:
        report = _read_json(Path(str(run["report_path"])))
        native = evaluate_vton_with_native(
            person_image_path=person_image,
            garment_image_path=garment_image,
            output_image_path=run["output_path"],
            overlay=report["preprocessing"]["overlay"],
            preferences=preferences,
            fairness_slices=fairness_slices,
            native_cli=args.native_cli,
        )
        runs.append(
            {
                "name": run["name"],
                "output_path": run["output_path"],
                "native": native,
            }
        )

    best = max(
        (run for run in runs if run["native"].get("available")),
        key=lambda run: float(run["native"].get("quality_index", 0.0)),
    )
    native_best = best["native"]
    model_card_updated = _update_model_card(args.model_card, best["name"], native_best, study)
    checks = {
        "native_vton_eval_available": all(bool(run["native"].get("available")) for run in runs),
        "identity_embedding_distance_present": "identity" in native_best and "embedding_distance" in native_best["identity"],
        "masked_garment_fidelity_present": "garment_fidelity" in native_best,
        "pose_consistency_present": "pose_consistency" in native_best,
        "fairness_audit_present": bool(native_best.get("fairness", {}).get("available")),
        "fairness_gap_within_threshold": bool(native_best.get("fairness", {}).get("passed")),
        "bradley_terry_ranking_present": bool(native_best.get("preference_ranking", {}).get("available")),
        "model_card_updated": model_card_updated,
    }
    report = {
        "schema_version": "tryops.vton_advanced_eval_report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "comparison_artifact": str(args.comparison),
        "study_artifact": str(args.study),
        "native_cli": str(args.native_cli),
        "research_sources": {
            "identity_embedding_target": "https://openaccess.thecvf.com/content_CVPR_2019/html/Deng_ArcFace_Additive_Angular_Margin_Loss_for_Deep_Face_Recognition_CVPR_2019_paper.html",
            "perceptual_similarity_target": "https://arxiv.org/abs/1801.03924",
            "bradley_terry_ranking": "https://doi.org/10.1093/biomet/39.3-4.324",
        },
        "checks": checks,
        "passed": all(checks.values()),
        "winner_by_quality_index": best["name"],
        "winner_by_bradley_terry": _bt_winner(native_best),
        "runs": runs,
        "limitations": [
            "Local identity uses a dependency-free face-region embedding proxy; production should use a pinned neural face-embedding model such as ArcFace/InsightFace.",
            "Local garment fidelity uses masked RGB/perceptual proxies; production should add LPIPS or another learned perceptual metric.",
            "Fairness slices are seeded smoke evidence and must be replaced by a licensed, representative evaluation set before customer claims.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"checks": checks, "passed": report["passed"], "winner": best["name"]}, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bt_winner(native: dict[str, Any]) -> str:
    ranking = native.get("preference_ranking", {}).get("ranking", [])
    if not ranking:
        return "unknown"
    return str(ranking[0]["item"])


def _update_model_card(model_card: Path, run_name: str, native: dict[str, Any], study: dict[str, Any]) -> bool:
    if not model_card.exists():
        return False
    fairness = native.get("fairness", {})
    ranking = native.get("preference_ranking", {}).get("ranking", [])
    top_rank = ranking[0]["item"] if ranking else "unknown"
    section = f"""{SECTION_TITLE}

- Native report schema: `{native.get("schema_version", "tryops.native_vton_eval.v1")}`
- Best local run: `{run_name}`
- Identity embedding proxy score: {native.get("identity", {}).get("score")}
- Garment-region masked fidelity score: {native.get("garment_fidelity", {}).get("score")}
- Pose-consistency score: {native.get("pose_consistency", {}).get("score")}
- Fairness slice audit: skin-tone gap {fairness.get("skin_tone_gap")}, body-type gap {fairness.get("body_type_gap")}, passed {fairness.get("passed")}
- Bradley-Terry preference winner: `{top_rank}` from `{study.get("study_id", "unknown")}`

Bias and limitation notes:

- The identity score is a native face-region embedding proxy; production identity claims require a pinned neural face-embedding model and consent-aware evaluation policy.
- The fairness slices are a seeded local smoke fixture, not a representative demographic audit.
- Human review is still required for identity shift, body-shape distortion, garment misrepresentation, and cultural clothing edge cases.
"""
    text = model_card.read_text(encoding="utf-8")
    if SECTION_TITLE in text:
        text = text.split(SECTION_TITLE, 1)[0].rstrip() + "\n\n" + section
    else:
        text = text.rstrip() + "\n\n" + section
    model_card.write_text(text, encoding="utf-8")
    return True


if __name__ == "__main__":
    raise SystemExit(main())
