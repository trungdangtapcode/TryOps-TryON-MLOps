#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FASHN_SRC = ROOT / "artifacts" / "external" / "fashn-vton-1.5" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if FASHN_SRC.exists() and str(FASHN_SRC) not in sys.path:
    sys.path.insert(0, str(FASHN_SRC))

from tryops.pipelines.data_ingestion import sha256_file  # noqa: E402
from tryops.run_context import build_run_context  # noqa: E402
from tryops.simple_image import RgbImage, write_png_rgb  # noqa: E402


DEFAULT_WEIGHTS_DIR = ROOT / "artifacts" / "models" / "fashn-vton-1.5"


class FashnVtonRunner:
    def __init__(self, *, weights_dir: str | Path = DEFAULT_WEIGHTS_DIR, device: str | None = "cuda") -> None:
        self.weights_dir = Path(weights_dir)
        self.device = device
        self._pipeline: Any | None = None
        self._load_ms: float | None = None

    def load(self) -> float:
        if self._pipeline is not None:
            return 0.0
        if not self.weights_dir.exists():
            raise FileNotFoundError(
                f"FASHN weights are missing at {self.weights_dir}. "
                "Run `make fashn-vton-download` first."
            )
        from fashn_vton import TryOnPipeline

        started = perf_counter()
        self._pipeline = TryOnPipeline(weights_dir=str(self.weights_dir), device=self.device)
        self._load_ms = round((perf_counter() - started) * 1000.0, 3)
        return self._load_ms

    def run(
        self,
        *,
        person_image_path: str | Path,
        garment_image_path: str | Path,
        output_image_path: str | Path,
        category: str = "tops",
        garment_photo_type: str = "model",
        num_timesteps: int = 50,
        guidance_scale: float = 1.5,
        seed: int = 555,
        segmentation_free: bool = True,
        num_samples: int = 1,
    ) -> dict[str, Any]:
        person_path = Path(person_image_path)
        garment_path = Path(garment_image_path)
        output_path = Path(output_image_path)
        if not person_path.exists():
            raise FileNotFoundError(f"person image does not exist: {person_path}")
        if not garment_path.exists():
            raise FileNotFoundError(f"garment image does not exist: {garment_path}")

        run_context = build_run_context(run_name="vton-fashn-v1.5")
        started = perf_counter()
        load_ms = self.load()

        image_load_started = perf_counter()
        person_image = Image.open(person_path).convert("RGB")
        garment_image = Image.open(garment_path).convert("RGB")
        image_load_ms = round((perf_counter() - image_load_started) * 1000.0, 3)

        torch = _optional_torch()
        if torch is not None and torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()

        inference_started = perf_counter()
        result = self._pipeline(
            person_image=person_image,
            garment_image=garment_image,
            category=category,
            garment_photo_type=garment_photo_type,
            num_samples=num_samples,
            num_timesteps=num_timesteps,
            guidance_scale=guidance_scale,
            seed=seed,
            segmentation_free=segmentation_free,
        )
        inference_ms = round((perf_counter() - inference_started) * 1000.0, 3)

        output_write_started = perf_counter()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_image = result.images[0].convert("RGB")
        write_png_rgb(output_path, RgbImage(output_image.width, output_image.height, output_image.tobytes()))
        output_write_ms = round((perf_counter() - output_write_started) * 1000.0, 3)
        latency_ms = round((perf_counter() - started) * 1000.0, 3)

        peak_vram_gb = None
        device_name = None
        if torch is not None and torch.cuda.is_available():
            peak_vram_gb = round(torch.cuda.max_memory_allocated() / 1e9, 6)
            device_name = torch.cuda.get_device_name(0)

        report = {
            "schema_version": "tryops.vton_fashn.v1",
            "created_at": datetime.now(UTC).isoformat(),
            "run_context": run_context,
            "model": {
                "name": "fashn-ai/fashn-vton-1.5",
                "version": "1.5.0",
                "type": "maskless_pixel_space_vton",
                "adapter": "fashn-vton-http",
                "weights_dir": str(self.weights_dir),
            },
            "inputs": {
                "person": {
                    "path": str(person_path),
                    "checksum": sha256_file(person_path),
                    "width": person_image.width,
                    "height": person_image.height,
                },
                "garment": {
                    "path": str(garment_path),
                    "checksum": sha256_file(garment_path),
                    "width": garment_image.width,
                    "height": garment_image.height,
                },
            },
            "preprocessing": {
                "category": category,
                "garment_photo_type": garment_photo_type,
                "segmentation_free": segmentation_free,
                "masking": "fashn-maskless-pipeline",
            },
            "output": {
                "path": str(output_path),
                "width": output_image.width,
                "height": output_image.height,
                "format": "png",
                "checksum": sha256_file(output_path),
            },
            "metrics": {
                "latency_ms": latency_ms,
                "model_load_ms": load_ms,
                "inference_ms": inference_ms,
                "peak_vram_gb": peak_vram_gb,
                "gpu_memory_gb": peak_vram_gb,
                "device": device_name,
                "stage_latency_ms": {
                    "model_load": load_ms,
                    "image_load": image_load_ms,
                    "inference": inference_ms,
                    "output_write": output_write_ms,
                },
            },
            "lineage": {
                "run_id": run_context["run_id"],
                "trace_id": run_context["trace_id"],
                "person_checksum": sha256_file(person_path),
                "garment_checksum": sha256_file(garment_path),
                "output_checksum": sha256_file(output_path),
                "adapter": "scripts.run_fashn_vton_single.FashnVtonRunner",
            },
        }
        output_path.with_suffix(output_path.suffix + ".json").write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return report


def _optional_torch() -> Any | None:
    try:
        import torch
    except ImportError:
        return None
    return torch


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one real FASHN VTON v1.5 inference.")
    parser.add_argument("--person", type=Path, required=True)
    parser.add_argument("--garment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weights-dir", type=Path, default=DEFAULT_WEIGHTS_DIR)
    parser.add_argument("--category", choices=["tops", "bottoms", "one-pieces"], default="tops")
    parser.add_argument("--garment-photo-type", choices=["model", "flat-lay"], default="model")
    parser.add_argument("--num-timesteps", type=int, default=50)
    parser.add_argument("--guidance-scale", type=float, default=1.5)
    parser.add_argument("--seed", type=int, default=555)
    parser.add_argument("--device", default=os.environ.get("TRYOPS_FASHN_VTON_DEVICE", "cuda"))
    parser.add_argument("--no-segmentation-free", action="store_false", dest="segmentation_free", default=True)
    args = parser.parse_args()

    runner = FashnVtonRunner(weights_dir=args.weights_dir, device=args.device)
    report = runner.run(
        person_image_path=args.person,
        garment_image_path=args.garment,
        output_image_path=args.output,
        category=args.category,
        garment_photo_type=args.garment_photo_type,
        num_timesteps=args.num_timesteps,
        guidance_scale=args.guidance_scale,
        seed=args.seed,
        segmentation_free=args.segmentation_free,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
