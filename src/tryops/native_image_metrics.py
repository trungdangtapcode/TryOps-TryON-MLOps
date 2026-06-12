from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tryops.simple_image import RgbImage


DEFAULT_NATIVE_IMAGE_METRICS_CLI = Path("artifacts/native/tryops_image_metrics_cli")


def serialize_images_for_native(reference: RgbImage, candidate: RgbImage) -> str:
    if reference.width != candidate.width or reference.height != candidate.height:
        raise ValueError("native image metrics require same-sized images")
    return "\n".join(
        [
            f"reference.width={reference.width}",
            f"reference.height={reference.height}",
            f"reference.pixels_hex={reference.pixels.hex()}",
            f"candidate.width={candidate.width}",
            f"candidate.height={candidate.height}",
            f"candidate.pixels_hex={candidate.pixels.hex()}",
            "",
        ]
    )


def evaluate_with_native_image_metrics(
    reference: RgbImage,
    candidate: RgbImage,
    *,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_IMAGE_METRICS_CLI", DEFAULT_NATIVE_IMAGE_METRICS_CLI))
    if not path.exists():
        return {
            "available": False,
            "cli_path": str(path),
            "reason": "native image metrics CLI not found",
        }
    payload = serialize_images_for_native(reference, candidate)
    completed = subprocess.run(
        [str(path)],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return {
            "available": True,
            "cli_path": str(path),
            "returncode": completed.returncode,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    metrics = json.loads(completed.stdout)
    metrics["available"] = True
    metrics["cli_path"] = str(path)
    metrics["returncode"] = completed.returncode
    return metrics
