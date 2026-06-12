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

from tryops.pipelines.data_ingestion import sha256_file  # noqa: E402
from tryops.simple_image import RgbImage, solid_rgb, write_png_rgb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create deterministic synthetic VTON demo images.")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/demo/vton"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    person_path = args.output_dir / "person.png"
    garment_path = args.output_dir / "garment.png"
    write_png_rgb(person_path, _person_image())
    write_png_rgb(garment_path, _garment_image())
    manifest = {
        "person_image": str(person_path),
        "garment_image": str(garment_path),
        "person_checksum": sha256_file(person_path),
        "garment_checksum": sha256_file(garment_path),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def _person_image() -> RgbImage:
    image = bytearray(solid_rgb(180, 240, (235, 238, 242)).pixels)
    width = 180
    for y in range(36, 220):
        for x in range(54, 126):
            index = (y * width + x) * 3
            image[index : index + 3] = bytes([210, 180, 150])
    for y in range(70, 220):
        for x in range(40, 140):
            if 50 <= x <= 130:
                index = (y * width + x) * 3
                image[index : index + 3] = bytes([180, 190, 205])
    return RgbImage(width=180, height=240, pixels=bytes(image))


def _garment_image() -> RgbImage:
    image = bytearray(solid_rgb(96, 96, (40, 80, 190)).pixels)
    width = 96
    for y in range(0, 96):
        for x in range(0, 96):
            if x % 16 < 4 or y % 20 < 3:
                index = (y * width + x) * 3
                image[index : index + 3] = bytes([245, 245, 255])
    return RgbImage(width=96, height=96, pixels=bytes(image))


if __name__ == "__main__":
    raise SystemExit(main())

