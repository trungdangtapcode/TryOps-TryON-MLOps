from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from tryops.native_vton_preprocess import evaluate_with_native_vton_preprocess
from tryops.pipelines.data_ingestion import sha256_file
from tryops.simple_image import RgbImage, read_png_rgb, write_png_rgb


def build_vton_optional_preprocessing(
    *,
    person_image_path: str | Path,
    garment_image_path: str | Path,
    cache_dir: str | Path,
    threshold: float = 32.0,
) -> dict[str, Any]:
    """Build optional VTON mask and pose preprocessing artifacts.

    CatVTON-style models reduce the need for parsing and pose preprocessing, but
    keeping these optional artifacts gives the platform a compatible path for
    models that still require masks or pose hints.
    """

    started = perf_counter()
    person_path = Path(person_image_path)
    garment_path = Path(garment_image_path)
    output_dir = Path(cache_dir) / "optional_preprocessing" / _cache_key(person_path, garment_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    person = read_png_rgb(person_path)
    garment = read_png_rgb(garment_path)
    person_mask = estimate_foreground_mask(person, threshold=threshold)
    garment_mask = estimate_foreground_mask(garment, threshold=threshold, fallback_to_full=True)

    person_mask_path = output_dir / "person_mask.png"
    garment_mask_path = output_dir / "garment_mask.png"
    write_png_rgb(person_mask_path, mask_to_image(person_mask, person.width, person.height))
    write_png_rgb(garment_mask_path, mask_to_image(garment_mask, garment.width, garment.height))

    person_bbox = bounding_box(person_mask, person.width, person.height)
    garment_bbox = bounding_box(garment_mask, garment.width, garment.height)
    pose = estimate_pose_hints(person_bbox, person.width, person.height)
    report = {
        "schema_version": "tryops.vton_optional_preprocessing.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "cache_dir": str(output_dir),
        "threshold": threshold,
        "person_mask": {
            "path": str(person_mask_path),
            "checksum": sha256_file(person_mask_path),
            "bbox": person_bbox,
            "coverage": mask_coverage(person_mask),
        },
        "garment_mask": {
            "path": str(garment_mask_path),
            "checksum": sha256_file(garment_mask_path),
            "bbox": garment_bbox,
            "coverage": mask_coverage(garment_mask),
        },
        "pose_hints": pose,
        "native": {
            "person": evaluate_with_native_vton_preprocess(person, role="person"),
            "garment": evaluate_with_native_vton_preprocess(garment, role="garment"),
        },
        "latency_ms": round((perf_counter() - started) * 1000.0, 3),
    }
    (output_dir / "preprocessing.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def estimate_foreground_mask(
    image: RgbImage,
    *,
    threshold: float = 32.0,
    fallback_to_full: bool = False,
) -> list[bool]:
    background = estimate_background_rgb(image)
    mask: list[bool] = []
    for index in range(0, len(image.pixels), 3):
        rgb = (image.pixels[index], image.pixels[index + 1], image.pixels[index + 2])
        mask.append(color_distance(rgb, background) >= threshold)
    coverage = mask_coverage(mask)
    if fallback_to_full and (coverage < 0.05 or coverage > 0.98):
        return [True] * (image.width * image.height)
    return mask


def estimate_background_rgb(image: RgbImage) -> tuple[int, int, int]:
    samples: list[tuple[int, int, int]] = []
    coordinates = [
        (0, 0),
        (image.width - 1, 0),
        (0, image.height - 1),
        (image.width - 1, image.height - 1),
    ]
    for x, y in coordinates:
        index = (y * image.width + x) * 3
        samples.append((image.pixels[index], image.pixels[index + 1], image.pixels[index + 2]))
    red = round(sum(sample[0] for sample in samples) / len(samples))
    green = round(sum(sample[1] for sample in samples) / len(samples))
    blue = round(sum(sample[2] for sample in samples) / len(samples))
    return red, green, blue


def bounding_box(mask: list[bool], width: int, height: int) -> dict[str, int] | None:
    if len(mask) != width * height:
        raise ValueError("mask size does not match image dimensions")
    xs: list[int] = []
    ys: list[int] = []
    for index, value in enumerate(mask):
        if value:
            ys.append(index // width)
            xs.append(index % width)
    if not xs:
        return None
    return {
        "x": min(xs),
        "y": min(ys),
        "width": max(xs) - min(xs) + 1,
        "height": max(ys) - min(ys) + 1,
    }


def estimate_pose_hints(
    bbox: dict[str, int] | None,
    image_width: int,
    image_height: int,
) -> dict[str, Any]:
    if bbox is None:
        return {
            "available": False,
            "method": "heuristic_foreground_bbox",
            "confidence": 0.0,
            "keypoints": {},
        }
    x = bbox["x"]
    y = bbox["y"]
    width = bbox["width"]
    height = bbox["height"]
    center_x = x + width / 2.0
    keypoints = {
        "neck": _point(center_x, y + height * 0.18),
        "left_shoulder": _point(x + width * 0.24, y + height * 0.28),
        "right_shoulder": _point(x + width * 0.76, y + height * 0.28),
        "torso_center": _point(center_x, y + height * 0.50),
        "left_hip": _point(x + width * 0.32, y + height * 0.75),
        "right_hip": _point(x + width * 0.68, y + height * 0.75),
    }
    bbox_area = width * height
    image_area = image_width * image_height
    confidence = min(0.95, max(0.1, bbox_area / max(1, image_area)))
    return {
        "available": True,
        "method": "heuristic_foreground_bbox",
        "confidence": round(confidence, 6),
        "keypoints": keypoints,
    }


def mask_to_image(mask: list[bool], width: int, height: int) -> RgbImage:
    if len(mask) != width * height:
        raise ValueError("mask size does not match image dimensions")
    pixels = bytearray(width * height * 3)
    for index, value in enumerate(mask):
        target = index * 3
        color = 255 if value else 0
        pixels[target : target + 3] = bytes([color, color, color])
    return RgbImage(width=width, height=height, pixels=bytes(pixels))


def mask_coverage(mask: list[bool]) -> float:
    if not mask:
        return 0.0
    return round(sum(1 for value in mask if value) / len(mask), 6)


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(3)))


def _point(x: float, y: float) -> dict[str, int]:
    return {"x": math.floor(x + 0.5), "y": math.floor(y + 0.5)}


def _cache_key(person_path: Path, garment_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(sha256_file(person_path).encode("utf-8"))
    digest.update(b"\n")
    digest.update(sha256_file(garment_path).encode("utf-8"))
    return digest.hexdigest()[:32]
