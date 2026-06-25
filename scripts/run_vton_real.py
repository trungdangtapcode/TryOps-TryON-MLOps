#!/usr/bin/env python3
"""Run real diffusion-based VTON (the VTON real tranche)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.vton_real import run_real_vton  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Real diffusion-based Virtual Try-On.")
    parser.add_argument("person_image", type=Path)
    parser.add_argument("garment_image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("artifacts/cache/vton_preflight"))
    parser.add_argument("--prompt", default="a person wearing the garment, photorealistic, high quality")
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--strength", type=float, default=0.75)
    args = parser.parse_args()

    report = run_real_vton(
        person_image_path=args.person_image,
        garment_image_path=args.garment_image,
        output_image_path=args.output,
        cache_dir=args.cache_dir,
        prompt=args.prompt,
        steps=args.steps,
        strength=args.strength,
    )
    m, metrics = report["model"], report["metrics"]
    print(f"adapter: {report['lineage']['adapter']}")
    print(f"model: {m['name']} ({m['type']})")
    print(f"latency_ms: {metrics.get('latency_ms')}  gpu_memory_gb: {metrics.get('gpu_memory_gb')}")
    print(f"output: {report['output']['path']} ({report['output']['width']}x{report['output']['height']})")
    print(json.dumps({"output_checksum": report["output"]["checksum"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
