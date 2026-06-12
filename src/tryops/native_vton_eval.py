from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tryops.simple_image import RgbImage, read_png_rgb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NATIVE_VTON_EVAL_CLI = ROOT / "artifacts" / "native" / "tryops_vton_eval_cli"


def evaluate_vton_with_native(
    *,
    person_image_path: str | Path,
    garment_image_path: str | Path,
    output_image_path: str | Path,
    overlay: dict[str, Any],
    preferences: list[dict[str, Any]] | None = None,
    fairness_slices: list[dict[str, Any]] | None = None,
    native_cli: str | Path | None = None,
) -> dict[str, Any]:
    cli = _native_cli_path(native_cli)
    if not cli.exists():
        return {
            "schema_version": "tryops.native_vton_eval.v1",
            "available": False,
            "reason": f"native VTON eval CLI not found at {cli}",
        }

    person = read_png_rgb(person_image_path)
    garment = read_png_rgb(garment_image_path)
    output = read_png_rgb(output_image_path)
    wire = serialize_vton_eval_for_native(
        person=person,
        garment=garment,
        output=output,
        overlay=overlay,
        preferences=preferences or [],
        fairness_slices=fairness_slices or [],
    )
    try:
        completed = subprocess.run(
            [str(cli)],
            input=wire,
            text=True,
            check=True,
            capture_output=True,
            timeout=5,
        )
        result = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {
            "schema_version": "tryops.native_vton_eval.v1",
            "available": False,
            "reason": str(exc),
        }
    result["available"] = True
    result["cli_path"] = str(cli)
    return result


def serialize_vton_eval_for_native(
    *,
    person: RgbImage,
    garment: RgbImage,
    output: RgbImage,
    overlay: dict[str, Any],
    preferences: list[dict[str, Any]],
    fairness_slices: list[dict[str, Any]],
) -> str:
    if person.width != output.width or person.height != output.height:
        raise ValueError("person and output images must have matching dimensions")
    lines = []
    lines.extend(_image_lines("person", person))
    lines.extend(_image_lines("garment", garment))
    lines.extend(_image_lines("output", output))
    for key in ("x", "y", "width", "height"):
        lines.append(f"overlay.{key}={int(overlay[key])}")
    lines.append(f"preference.count={len(preferences)}")
    for index, preference in enumerate(preferences):
        prefix = f"preference.{index}"
        lines.append(f"{prefix}.winner={preference['winner']}")
        lines.append(f"{prefix}.loser={preference['loser']}")
        lines.append(f"{prefix}.weight={float(preference.get('weight', 1.0))}")
    lines.append(f"slice.count={len(fairness_slices)}")
    for index, fairness_slice in enumerate(fairness_slices):
        prefix = f"slice.{index}"
        lines.append(f"{prefix}.skin_tone={fairness_slice['skin_tone']}")
        lines.append(f"{prefix}.body_type={fairness_slice['body_type']}")
        lines.append(f"{prefix}.quality={float(fairness_slice['quality'])}")
    return "\n".join(lines) + "\n"


def _image_lines(prefix: str, image: RgbImage) -> list[str]:
    return [
        f"{prefix}.width={image.width}",
        f"{prefix}.height={image.height}",
        f"{prefix}.pixels_hex={image.pixels.hex()}",
    ]


def _native_cli_path(native_cli: str | Path | None) -> Path:
    if native_cli is not None:
        return Path(native_cli)
    configured = os.getenv("TRYOPS_NATIVE_VTON_EVAL_CLI", "").strip()
    return Path(configured) if configured else DEFAULT_NATIVE_VTON_EVAL_CLI
