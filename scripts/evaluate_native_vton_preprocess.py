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

from tryops.native_vton_preprocess import evaluate_with_native_vton_preprocess  # noqa: E402
from tryops.simple_image import read_png_rgb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one PNG with the native VTON preprocessing CLI.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--role", choices=["person", "garment"], required=True)
    parser.add_argument("--cli", type=Path, default=Path("artifacts/native/tryops_vton_preprocess_cli"))
    args = parser.parse_args()

    image = read_png_rgb(args.image)
    result = evaluate_with_native_vton_preprocess(image, role=args.role, cli_path=args.cli)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("available") and result.get("returncode") == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
