from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any

ALLOWED_IMAGE_FORMATS = {"png", "jpeg"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
PNG_COLOR_TYPES = {
    0: "grayscale",
    2: "rgb",
    3: "indexed",
    4: "grayscale_alpha",
    6: "rgba",
}


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def detect_image_format(path: str | Path) -> str | None:
    file_path = Path(path)
    header = file_path.read_bytes()[:16]
    if header.startswith(PNG_SIGNATURE):
        return "png"
    if header.startswith(JPEG_SIGNATURE):
        return "jpeg"
    return None


def read_image_metadata(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    image_format = detect_image_format(file_path)
    if image_format == "png":
        return _read_png_metadata(file_path)
    if image_format == "jpeg":
        return _read_jpeg_metadata(file_path)
    return {"format": image_format, "width": None, "height": None, "color_mode": None}


def validate_image_file(
    path: str | Path,
    *,
    max_size_bytes: int = 10 * 1024 * 1024,
    min_width: int = 64,
    min_height: int = 64,
    max_width: int = 4096,
    max_height: int = 4096,
) -> dict[str, Any]:
    file_path = Path(path)
    errors: list[str] = []
    if not file_path.exists():
        return {"passed": False, "errors": ["file does not exist"], "format": None, "size_bytes": 0}
    if not file_path.is_file():
        return {"passed": False, "errors": ["path is not a file"], "format": None, "size_bytes": 0}

    size_bytes = file_path.stat().st_size
    metadata = read_image_metadata(file_path)
    image_format = metadata["format"]
    if image_format not in ALLOWED_IMAGE_FORMATS:
        errors.append("unsupported or corrupted image format")
    width = metadata["width"]
    height = metadata["height"]
    if width is None or height is None:
        errors.append("image dimensions could not be read")
    else:
        if width < min_width or height < min_height:
            errors.append(f"image dimensions {width}x{height} below minimum {min_width}x{min_height}")
        if width > max_width or height > max_height:
            errors.append(f"image dimensions {width}x{height} exceed maximum {max_width}x{max_height}")
    if size_bytes > max_size_bytes:
        errors.append(f"file size {size_bytes} exceeds limit {max_size_bytes}")

    return {
        "passed": not errors,
        "errors": errors,
        "format": image_format,
        "width": width,
        "height": height,
        "color_mode": metadata["color_mode"],
        "size_bytes": size_bytes,
    }


def build_manifest_entry(
    *,
    item_id: str,
    path: str | Path,
    split: str,
    license_name: str,
) -> dict[str, Any]:
    file_path = Path(path)
    validation = validate_image_file(file_path)
    if not validation["passed"]:
        raise ValueError(f"invalid image '{file_path}': {', '.join(validation['errors'])}")
    return {
        "id": item_id,
        "path": str(file_path),
        "split": split,
        "checksum": sha256_file(file_path),
        "license": license_name,
        "format": validation["format"],
        "width": validation["width"],
        "height": validation["height"],
        "color_mode": validation["color_mode"],
        "size_bytes": validation["size_bytes"],
    }


def _read_png_metadata(path: Path) -> dict[str, Any]:
    data = path.read_bytes()[:32]
    if len(data) < 26 or not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        return {"format": "png", "width": None, "height": None, "color_mode": None}
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    return {
        "format": "png",
        "width": int(width),
        "height": int(height),
        "color_mode": PNG_COLOR_TYPES.get(color_type, f"unknown_{color_type}"),
    }


def _read_jpeg_metadata(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if not data.startswith(JPEG_SIGNATURE):
        return {"format": "jpeg", "width": None, "height": None, "color_mode": None}

    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2

        while marker == 0xFF and index < len(data):
            marker = data[index]
            index += 1

        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[index : index + 2])[0]
        if segment_length < 2 or index + segment_length > len(data):
            break

        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            segment = data[index + 2 : index + segment_length]
            if len(segment) < 6:
                break
            height, width = struct.unpack(">HH", segment[1:5])
            components = segment[5]
            return {
                "format": "jpeg",
                "width": int(width),
                "height": int(height),
                "color_mode": "grayscale" if components == 1 else "rgb" if components == 3 else f"{components}_component",
            }

        index += segment_length

    return {"format": "jpeg", "width": None, "height": None, "color_mode": None}
