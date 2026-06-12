from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_REAL_VTON_URL = "http://host.docker.internal:18101"


class RealVtonUnavailableError(RuntimeError):
    """Raised when a real VTON adapter is selected but the model service is unavailable."""


def run_remote_fashn_vton(
    *,
    person_image_path: str | Path,
    garment_image_path: str | Path,
    output_image_path: str | Path,
    cache_dir: str | Path,
    timeout_ms: int,
    category: str = "tops",
    garment_photo_type: str = "model",
    num_timesteps: int = 50,
    guidance_scale: float = 1.5,
    seed: int = 555,
    segmentation_free: bool = True,
) -> dict[str, Any]:
    """Run FASHN VTON through the host-side GPU model service.

    Docker GPU runtime is not guaranteed in local demos, so the API calls a host
    service that owns CUDA and model weights. This path intentionally does not
    fall back to the deterministic compositor.
    """

    base_url = os.environ.get("TRYOPS_REAL_VTON_URL", DEFAULT_REAL_VTON_URL).rstrip("/")
    payload = {
        "person_image_path": str(person_image_path),
        "garment_image_path": str(garment_image_path),
        "output_image_path": str(output_image_path),
        "cache_dir": str(cache_dir),
        "category": category,
        "garment_photo_type": garment_photo_type,
        "num_timesteps": num_timesteps,
        "guidance_scale": guidance_scale,
        "seed": seed,
        "segmentation_free": segmentation_free,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/v1/vton/infer",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, timeout_ms / 1000.0)) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace") or str(exc)
        raise RealVtonUnavailableError(f"FASHN VTON service rejected request: {message}") from exc
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise RealVtonUnavailableError(
            f"FASHN VTON service unavailable at {base_url}. Start it with `make fashn-vton-service`."
        ) from exc

    if data.get("status") != "completed" or not isinstance(data.get("report"), dict):
        raise RealVtonUnavailableError(data.get("message") or data.get("error") or "FASHN VTON service failed")
    return data["report"]


run_remote_catvton = run_remote_fashn_vton
