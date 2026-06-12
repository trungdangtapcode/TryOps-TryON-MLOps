#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_image_metrics import evaluate_with_native_image_metrics  # noqa: E402
from tryops.pipelines.image_metrics import compare_images  # noqa: E402
from tryops.simple_image import read_png_rgb, resize_nearest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate two PNG files with the native image metrics CLI.")
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--cli", type=Path, default=Path("artifacts/native/tryops_image_metrics_cli"))
    args = parser.parse_args()

    reference = read_png_rgb(args.reference)
    candidate = read_png_rgb(args.candidate)
    if reference.width != candidate.width or reference.height != candidate.height:
        candidate = resize_nearest(candidate, reference.width, reference.height)
    native = evaluate_with_native_image_metrics(reference, candidate, cli_path=args.cli)
    python_metrics = compare_images(reference, candidate)
    result = {
        "native": native,
        "python": python_metrics,
        "native_available": bool(native.get("available")),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if native.get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
