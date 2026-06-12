from __future__ import annotations

from pathlib import Path
from typing import Any

from tryops.native_image_metrics import evaluate_with_native_image_metrics
from tryops.simple_image import read_png_rgb


def build_native_vton_execution_evidence(
    *,
    report: dict[str, Any],
    person_image_path: str | Path,
) -> dict[str, Any]:
    """Surface native VTON evidence for API/job responses and request detail rows."""

    preprocessing = _native_preprocessing_from_report(report)
    image_metrics = _native_output_metrics(
        person_image_path=person_image_path,
        output_image_path=str(report.get("output", {}).get("path", "")),
    )
    quality_score = quality_score_from_native_metrics(image_metrics)
    return {
        "schema_version": "tryops.native_vton_execution.v1",
        "preprocessing": preprocessing,
        "image_metrics": image_metrics,
        "quality_score": quality_score,
        "lineage": {
            "person_checksum": report.get("lineage", {}).get("person_checksum"),
            "output_checksum": report.get("lineage", {}).get("output_checksum"),
            "native_preprocess_cli": preprocessing.get("cli_paths", {}).get("person"),
            "native_image_metrics_cli": image_metrics.get("cli_path"),
        },
    }


def quality_score_from_native_metrics(metrics: dict[str, Any]) -> float | None:
    if not metrics.get("available") or "error" in metrics:
        return None
    value = metrics.get("dhash_similarity")
    if not isinstance(value, (int, float)):
        return None
    return round(max(0.0, min(1.0, float(value))), 6)


def _native_preprocessing_from_report(report: dict[str, Any]) -> dict[str, Any]:
    native = (
        report.get("preprocessing", {})
        .get("optional_segmentation", {})
        .get("native", {})
    )
    person = dict(native.get("person") or {})
    garment = dict(native.get("garment") or {})
    return {
        "schema_version": "tryops.native_vton_preprocess_bridge.v1",
        "person": person,
        "garment": garment,
        "available": bool(person.get("available")) and bool(garment.get("available")),
        "cli_paths": {
            "person": person.get("cli_path"),
            "garment": garment.get("cli_path"),
        },
        "person_bbox": person.get("bbox"),
        "garment_bbox": garment.get("bbox"),
        "person_pose": person.get("pose_hints"),
        "person_coverage": person.get("coverage"),
        "garment_coverage": garment.get("coverage"),
    }


def _native_output_metrics(
    *,
    person_image_path: str | Path,
    output_image_path: str | Path,
) -> dict[str, Any]:
    if not output_image_path:
        return {"available": False, "reason": "VTON output path missing"}
    try:
        person = read_png_rgb(person_image_path)
        output = read_png_rgb(output_image_path)
        return evaluate_with_native_image_metrics(person, output)
    except (OSError, ValueError) as exc:
        return {
            "available": False,
            "reason": str(exc),
            "person_image_path": str(person_image_path),
            "output_image_path": str(output_image_path),
        }
