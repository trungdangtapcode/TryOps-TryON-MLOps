from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from tryops.pipelines.data_ingestion import sha256_file
from tryops.pipelines.vton_preflight import build_vton_preflight
from tryops.pipelines.vton_preprocessing import build_vton_optional_preprocessing
from tryops.run_context import build_run_context
from tryops.simple_image import overlay, read_png_rgb, resize_nearest, write_png_rgb


def run_naive_overlay_baseline(
    *,
    person_image_path: str | Path,
    garment_image_path: str | Path,
    output_image_path: str | Path,
    cache_dir: str | Path,
    garment_width_ratio: float = 0.48,
    garment_height_ratio: float = 0.38,
    top_ratio: float = 0.26,
) -> dict[str, Any]:
    """Run a deterministic baseline that overlays a resized garment onto the torso region.

    This is intentionally simple. It exists to exercise the MLOps path before a real
    CatVTON or IDM-VTON adapter is available.
    """

    run_context = build_run_context(run_name="vton-naive-overlay-baseline")
    started = perf_counter()
    preflight_started = perf_counter()
    preflight = build_vton_preflight(
        person_image_path=person_image_path,
        garment_image_path=garment_image_path,
        cache_dir=cache_dir,
    )
    preflight_ms = round((perf_counter() - preflight_started) * 1000.0, 3)
    if not preflight["passed"]:
        raise ValueError(f"VTON preflight failed: {'; '.join(preflight['errors'])}")
    if preflight["person"]["format"] != "png" or preflight["garment"]["format"] != "png":
        raise ValueError("naive overlay baseline currently supports PNG inputs only")

    optional_preprocessing_started = perf_counter()
    optional_preprocessing = build_vton_optional_preprocessing(
        person_image_path=person_image_path,
        garment_image_path=garment_image_path,
        cache_dir=cache_dir,
    )
    optional_preprocessing_ms = round((perf_counter() - optional_preprocessing_started) * 1000.0, 3)

    image_load_started = perf_counter()
    person = read_png_rgb(person_image_path)
    garment = read_png_rgb(garment_image_path)
    image_load_ms = round((perf_counter() - image_load_started) * 1000.0, 3)
    generation_started = perf_counter()
    garment_width = max(1, round(person.width * garment_width_ratio))
    garment_height = max(1, round(person.height * garment_height_ratio))
    resized_garment = resize_nearest(garment, garment_width, garment_height)
    x = max(0, (person.width - garment_width) // 2)
    y = max(0, round(person.height * top_ratio))
    output = overlay(person, resized_garment, x=x, y=y)
    generation_ms = round((perf_counter() - generation_started) * 1000.0, 3)

    output_write_started = perf_counter()
    output_path = Path(output_image_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_png_rgb(output_path, output)
    output_write_ms = round((perf_counter() - output_write_started) * 1000.0, 3)
    latency_ms = round((perf_counter() - started) * 1000.0, 3)
    report = {
        "schema_version": "tryops.vton_baseline.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "run_context": run_context,
        "model": {
            "name": "naive-overlay-vton",
            "version": "0.1.0",
            "type": "deterministic_baseline",
        },
        "inputs": {
            "person": preflight["person"],
            "garment": preflight["garment"],
        },
        "preflight_cache_key": preflight["cache_key"],
        "preprocessing": {
            "person_normalization": {
                "output_width": person.width,
                "output_height": person.height,
                "color_mode": "rgb",
            },
            "garment_normalization": {
                "output_width": garment_width,
                "output_height": garment_height,
                "color_mode": "rgb",
                "resize": "nearest",
            },
            "optional_segmentation": {
                "person_mask": optional_preprocessing["person_mask"],
                "garment_mask": optional_preprocessing["garment_mask"],
                "native": optional_preprocessing["native"],
            },
            "optional_pose": optional_preprocessing["pose_hints"],
            "optional_preprocessing_cache_dir": optional_preprocessing["cache_dir"],
            "overlay": {
                "x": x,
                "y": y,
                "width": garment_width,
                "height": garment_height,
            },
        },
        "output": {
            "path": str(output_path),
            "width": output.width,
            "height": output.height,
            "format": "png",
            "checksum": sha256_file(output_path),
        },
        "metrics": {
            "latency_ms": latency_ms,
            "stage_latency_ms": {
                "preflight": preflight_ms,
                "optional_preprocessing": optional_preprocessing_ms,
                "image_load": image_load_ms,
                "generation": generation_ms,
                "output_write": output_write_ms,
            },
        },
        "lineage": {
            "run_id": run_context["run_id"],
            "trace_id": run_context["trace_id"],
            "person_checksum": preflight["person"]["checksum"],
            "garment_checksum": preflight["garment"]["checksum"],
            "person_mask_checksum": optional_preprocessing["person_mask"]["checksum"],
            "garment_mask_checksum": optional_preprocessing["garment_mask"]["checksum"],
            "output_checksum": sha256_file(output_path),
            "adapter": "tryops.pipelines.vton_baseline.run_naive_overlay_baseline",
        },
    }
    report_path = output_path.with_suffix(output_path.suffix + ".json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
