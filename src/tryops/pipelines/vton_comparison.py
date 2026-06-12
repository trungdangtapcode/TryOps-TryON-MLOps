from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tryops.pipelines.garment_similarity import evaluate_garment_similarity
from tryops.pipelines.image_metrics import compare_png_files_with_native
from tryops.pipelines.vton_baseline import run_naive_overlay_baseline


DEFAULT_CONFIGS = [
    {
        "name": "naive_standard",
        "garment_width_ratio": 0.48,
        "garment_height_ratio": 0.38,
        "top_ratio": 0.26,
    },
    {
        "name": "naive_wide_lower",
        "garment_width_ratio": 0.62,
        "garment_height_ratio": 0.42,
        "top_ratio": 0.31,
    },
]


def compare_vton_baselines(
    *,
    person_image_path: str | Path,
    garment_image_path: str | Path,
    output_dir: str | Path,
    cache_dir: str | Path,
    configs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run two or more VTON baseline configurations and write comparison artifacts."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    configs = configs or DEFAULT_CONFIGS
    runs: list[dict[str, Any]] = []

    for config in configs:
        name = str(config["name"])
        report = run_naive_overlay_baseline(
            person_image_path=person_image_path,
            garment_image_path=garment_image_path,
            output_image_path=output_path / f"{name}.png",
            cache_dir=cache_dir,
            garment_width_ratio=float(config["garment_width_ratio"]),
            garment_height_ratio=float(config["garment_height_ratio"]),
            top_ratio=float(config["top_ratio"]),
        )
        metrics_against_person = compare_png_files_with_native(person_image_path, report["output"]["path"])
        garment_similarity = evaluate_garment_similarity(
            garment_image_path=garment_image_path,
            output_image_path=report["output"]["path"],
            overlay=report["preprocessing"]["overlay"],
        )
        runs.append(
            {
                "name": name,
                "config": dict(config),
                "report_path": f"{report['output']['path']}.json",
                "output_path": report["output"]["path"],
                "output_checksum": report["output"]["checksum"],
                "latency_ms": report["metrics"]["latency_ms"],
                "metrics_against_person": metrics_against_person,
                "garment_similarity": garment_similarity,
                "failure_labels": _heuristic_failure_labels(config),
            }
        )

    comparison = {
        "schema_version": "tryops.vton_comparison.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "person_image_path": str(person_image_path),
        "garment_image_path": str(garment_image_path),
        "runs": runs,
        "winner_by_structural_similarity": max(
            runs,
            key=lambda item: item["metrics_against_person"]["global_ssim_luma"],
        )["name"],
        "winner_by_perceptual_hash": max(
            runs,
            key=lambda item: item["metrics_against_person"]["dhash_similarity"],
        )["name"],
        "winner_by_garment_similarity_proxy": max(
            runs,
            key=lambda item: item["garment_similarity"]["proxy"]["score"],
        )["name"],
        "notes": [
            "Metrics are smoke-test proxies against the input person image, not final VTON quality.",
            "dHash and edge delta are dependency-free perceptual proxies, not replacements for LPIPS or CLIP.",
            "OpenCLIP garment similarity is optional and is reported only when neural dependencies and weights are available.",
            "Human review and CatVTON/IDM-VTON comparison are required before champion promotion.",
        ],
    }
    gallery = build_error_gallery(comparison)
    (output_path / "comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_path / "error_gallery.json").write_text(
        json.dumps(gallery, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return comparison


def build_error_gallery(comparison: dict[str, Any]) -> dict[str, Any]:
    examples: list[dict[str, Any]] = []
    for run in comparison["runs"]:
        for label in run["failure_labels"]:
            examples.append(
                {
                    "run": run["name"],
                    "label": label,
                    "output_path": run["output_path"],
                    "rationale": _label_rationale(label),
                }
            )
    return {
        "schema_version": "tryops.vton_error_gallery.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "examples": examples,
    }


def _heuristic_failure_labels(config: dict[str, Any]) -> list[str]:
    labels = ["edge_blending_failure"]
    if float(config["garment_width_ratio"]) > 0.58:
        labels.append("body_shape_distortion")
    if float(config["top_ratio"]) > 0.30:
        labels.append("pose_failure")
    return labels


def _label_rationale(label: str) -> str:
    rationales = {
        "edge_blending_failure": "Naive overlay has no generative blending or learned boundary repair.",
        "body_shape_distortion": "Wide overlay can cover body regions unrealistically.",
        "pose_failure": "Fixed overlay position does not follow estimated body pose.",
    }
    return rationales.get(label, "Failure label generated by baseline heuristic.")
