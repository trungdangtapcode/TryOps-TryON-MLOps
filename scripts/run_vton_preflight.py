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

from tryops.pipelines.vton_preflight import build_vton_preflight  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VTON preflight validation and cache metadata.")
    parser.add_argument("person_image", type=Path)
    parser.add_argument("garment_image", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path("artifacts/cache/vton_preflight"))
    args = parser.parse_args()

    report = build_vton_preflight(
        person_image_path=args.person_image,
        garment_image_path=args.garment_image,
        cache_dir=args.cache_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

