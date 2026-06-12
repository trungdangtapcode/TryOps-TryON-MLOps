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

from tryops.pipelines.vton_comparison import compare_vton_baselines  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare local VTON baseline configurations.")
    parser.add_argument("person_image", type=Path)
    parser.add_argument("garment_image", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/eval/vton_comparison"))
    parser.add_argument("--cache-dir", type=Path, default=Path("artifacts/cache/vton_preflight"))
    args = parser.parse_args()

    comparison = compare_vton_baselines(
        person_image_path=args.person_image,
        garment_image_path=args.garment_image,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
    )
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

