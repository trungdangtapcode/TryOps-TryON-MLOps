"""Real diffusion-based Virtual Try-On (the VTON real tranche).

Runs a genuine latent-diffusion try-on on
the GPU, behind the *same* ``tryops.vton_baseline.v1`` artifact contract. Method:
the garment is composited onto the person's torso region (preserving its pixels),
then Stable-Diffusion inpainting refines that region at partial strength so the
garment is conditioned on real pixels (not just a text prompt) and blended
photorealistically. This is an honest, low-VRAM real-diffusion baseline; dedicated
warping models (CatVTON, IDM-VTON) remain the higher-fidelity stretch.

This helper fails closed when torch, diffusers, CUDA, or model weights are
unavailable.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from tryops.energy import measure_energy
from tryops.pipelines.data_ingestion import sha256_file
from tryops.run_context import build_run_context

# Canonical community SD1.5 inpainting repo (ungated; stabilityai/* is gated).
DEFAULT_VTON_MODEL = "stable-diffusion-v1-5/stable-diffusion-inpainting"
REAL_ADAPTER = "tryops.pipelines.vton_real.run_real_vton"
_PIPE_CACHE: dict[str, Any] = {}


def real_vton_available() -> bool:
    try:
        import diffusers  # noqa: F401
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _load_pipe(model_id: str):
    if model_id in _PIPE_CACHE:
        return _PIPE_CACHE[model_id]
    import torch
    from diffusers import StableDiffusionInpaintPipeline

    pipe = StableDiffusionInpaintPipeline.from_pretrained(
        model_id, torch_dtype=torch.float16, safety_checker=None
    ).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    _PIPE_CACHE[model_id] = pipe
    return pipe


def _composite_and_mask(person_path, garment_path, *, width_ratio=0.48, height_ratio=0.38, top_ratio=0.26):
    """Overlay the garment on the person torso and build the inpaint mask (PIL)."""

    from PIL import Image

    person = Image.open(person_path).convert("RGB").resize((512, 512))
    garment = Image.open(garment_path).convert("RGB")
    gw = max(1, round(512 * width_ratio))
    gh = max(1, round(512 * height_ratio))
    garment = garment.resize((gw, gh))
    x = max(0, (512 - gw) // 2)
    y = max(0, round(512 * top_ratio))
    composite = person.copy()
    composite.paste(garment, (x, y))
    mask = Image.new("L", (512, 512), 0)
    from PIL import ImageDraw

    # Mask slightly tighter than the paste box so edges blend into the body.
    pad = 6
    ImageDraw.Draw(mask).rectangle([x + pad, y + pad, x + gw - pad, y + gh - pad], fill=255)
    return composite, mask, {"x": x, "y": y, "width": gw, "height": gh}


def run_real_vton(
    *,
    person_image_path: str | Path,
    garment_image_path: str | Path,
    output_image_path: str | Path,
    cache_dir: str | Path,
    prompt: str = "a person wearing the garment, photorealistic, high quality",
    steps: int = 25,
    strength: float = 0.75,
    guidance_scale: float = 7.5,
    model_id: str = DEFAULT_VTON_MODEL,
) -> dict[str, Any]:
    """Generate a real diffusion try-on without deterministic fallback."""

    output_path = Path(output_image_path)
    if not real_vton_available():
        raise RuntimeError("real VTON requires torch, diffusers, and CUDA")

    try:
        run_context = build_run_context(run_name="vton-real-diffusion-inpaint")
        composite, mask, region = _composite_and_mask(person_image_path, garment_image_path)
        pipe = _load_pipe(model_id)

        import torch

        def _generate():
            torch.cuda.reset_peak_memory_stats()
            with torch.no_grad():
                return pipe(
                    prompt=prompt,
                    image=composite,
                    mask_image=mask,
                    num_inference_steps=steps,
                    strength=strength,
                    guidance_scale=guidance_scale,
                ).images[0]

        started = perf_counter()
        out_image, energy = measure_energy(_generate, tokens=0)
        latency_ms = round((perf_counter() - started) * 1000.0, 3)
        gpu_vram_gb = round(torch.cuda.max_memory_allocated() / 1e9, 6)

        # Save via the project's filter-type-0 PNG writer so the lightweight
        # reader and the native C++ image-metrics CLI can consume the output.
        from tryops.simple_image import RgbImage, write_png_rgb

        output_path.parent.mkdir(parents=True, exist_ok=True)
        rgb = RgbImage(width=out_image.width, height=out_image.height,
                       pixels=out_image.convert("RGB").tobytes())
        write_png_rgb(output_path, rgb)
        checksum = sha256_file(output_path)

        report = {
            "schema_version": "tryops.vton_baseline.v1",
            "created_at": datetime.now(UTC).isoformat(),
            "run_context": run_context,
            "model": {
                "name": model_id,
                "version": "0.1.0",
                "type": "diffusion_inpaint_vton",
                "method": "garment-composite + SD1.5 inpaint refinement",
            },
            "inputs": {
                "person": {"path": str(person_image_path), "checksum": sha256_file(person_image_path)},
                "garment": {"path": str(garment_image_path), "checksum": sha256_file(garment_image_path)},
            },
            "preprocessing": {"inpaint_region": region, "prompt": prompt,
                              "steps": steps, "strength": strength, "guidance_scale": guidance_scale},
            "output": {
                "path": str(output_path),
                "width": out_image.width,
                "height": out_image.height,
                "format": "png",
                "checksum": checksum,
            },
            "metrics": {
                "latency_ms": latency_ms,
                "gpu_memory_gb": gpu_vram_gb,
                "energy": energy,
            },
            "lineage": {
                "run_id": run_context["run_id"],
                "trace_id": run_context["trace_id"],
                "person_checksum": sha256_file(person_image_path),
                "garment_checksum": sha256_file(garment_image_path),
                "output_checksum": checksum,
                "adapter": REAL_ADAPTER,
            },
        }
        report_path = output_path.with_suffix(output_path.suffix + ".json")
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return report
    except Exception as exc:
        raise RuntimeError(f"real VTON failed: {type(exc).__name__}: {exc}") from exc
