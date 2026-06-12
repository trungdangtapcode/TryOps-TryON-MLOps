from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tryops.simple_image import RgbImage


DEFAULT_NATIVE_VTON_PREPROCESS_CLI = Path("artifacts/native/tryops_vton_preprocess_cli")


def serialize_image_for_native_preprocess(image: RgbImage, *, role: str) -> str:
    if role not in {"person", "garment"}:
        raise ValueError("role must be 'person' or 'garment'")
    return "\n".join(
        [
            f"role={role}",
            f"width={image.width}",
            f"height={image.height}",
            f"pixels_hex={image.pixels.hex()}",
            "",
        ]
    )


def evaluate_with_native_vton_preprocess(
    image: RgbImage,
    *,
    role: str,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_VTON_PREPROCESS_CLI", DEFAULT_NATIVE_VTON_PREPROCESS_CLI))
    if not path.exists():
        return {
            "available": False,
            "cli_path": str(path),
            "reason": "native VTON preprocess CLI not found",
        }
    payload = serialize_image_for_native_preprocess(image, role=role)
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
    result = json.loads(completed.stdout)
    result["available"] = True
    result["cli_path"] = str(path)
    result["returncode"] = completed.returncode
    return result
