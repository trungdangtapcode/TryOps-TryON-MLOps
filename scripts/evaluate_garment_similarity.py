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

from tryops.pipelines.garment_similarity import evaluate_garment_similarity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate VTON garment preservation similarity.")
    parser.add_argument("garment_image", type=Path)
    parser.add_argument("output_image", type=Path)
    parser.add_argument("--report", type=Path, help="VTON baseline JSON report with overlay metadata.")
    parser.add_argument("--output", type=Path, help="Write the similarity report to this path.")
    parser.add_argument("--prompt", action="append", dest="prompts", help="Text prompt for optional OpenCLIP scoring.")
    parser.add_argument("--enable-clip", action="store_true", help="Run a neural CLIP backend.")
    parser.add_argument("--enable-openclip", action="store_true")
    parser.add_argument("--clip-backend", default=None, help="CLIP backend: auto, transformers_clip, or open_clip.")
    parser.add_argument("--clip-model", default="openai/clip-vit-base-patch32", help="Transformers CLIP model id.")
    args = parser.parse_args()

    overlay = None
    if args.report is not None:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        overlay = report["preprocessing"]["overlay"]

    result = evaluate_garment_similarity(
        garment_image_path=args.garment_image,
        output_image_path=args.output_image,
        overlay=overlay,
        text_prompts=args.prompts,
        enable_clip=args.enable_clip or None,
        enable_openclip=args.enable_openclip,
        clip_backend=args.clip_backend,
        transformers_clip_model=args.clip_model,
    )
    body = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body + "\n", encoding="utf-8")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
