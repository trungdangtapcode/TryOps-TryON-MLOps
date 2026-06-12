from __future__ import annotations

import binascii
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class RgbImage:
    width: int
    height: int
    pixels: bytes

    def __post_init__(self) -> None:
        expected = self.width * self.height * 3
        if len(self.pixels) != expected:
            raise ValueError(f"pixel buffer has {len(self.pixels)} bytes, expected {expected}")


def solid_rgb(width: int, height: int, rgb: tuple[int, int, int]) -> RgbImage:
    return RgbImage(width=width, height=height, pixels=bytes(rgb) * (width * height))


def read_png_rgb(path: str | Path) -> RgbImage:
    data = Path(path).read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")

    offset = len(PNG_SIGNATURE)
    width: int | None = None
    height: int | None = None
    color_type: int | None = None
    idat_parts: list[bytes] = []

    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length

        if chunk_type == b"IHDR":
            width, height = struct.unpack(">II", chunk_data[:8])
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
            if bit_depth != 8:
                raise ValueError("only 8-bit PNG images are supported")
            if color_type not in {0, 2, 6}:
                raise ValueError("only grayscale, RGB, and RGBA PNG images are supported")
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or color_type is None:
        raise ValueError("PNG IHDR chunk is missing")
    if not idat_parts:
        raise ValueError("PNG IDAT chunk is missing")

    decompressed = zlib.decompress(b"".join(idat_parts))
    channels = {0: 1, 2: 3, 6: 4}[color_type]
    row_bytes = width * channels
    expected = height * (1 + row_bytes)
    if len(decompressed) != expected:
        raise ValueError("unsupported PNG layout or corrupted IDAT data")

    rgb = bytearray(width * height * 3)
    source_offset = 0
    target_offset = 0
    for _row in range(height):
        filter_type = decompressed[source_offset]
        source_offset += 1
        if filter_type != 0:
            raise ValueError("only PNG filter type 0 is supported by the lightweight baseline")
        row = decompressed[source_offset : source_offset + row_bytes]
        source_offset += row_bytes
        if color_type == 0:
            for value in row:
                rgb[target_offset : target_offset + 3] = bytes([value, value, value])
                target_offset += 3
        elif color_type == 2:
            rgb[target_offset : target_offset + row_bytes] = row
            target_offset += row_bytes
        else:
            for index in range(0, len(row), 4):
                rgb[target_offset : target_offset + 3] = row[index : index + 3]
                target_offset += 3

    return RgbImage(width=width, height=height, pixels=bytes(rgb))


def write_png_rgb(path: str | Path, image: RgbImage) -> None:
    output = bytearray(PNG_SIGNATURE)
    ihdr = (
        struct.pack(">II", image.width, image.height)
        + bytes([8, 2, 0, 0, 0])
    )
    output.extend(_chunk(b"IHDR", ihdr))

    raw = bytearray()
    row_bytes = image.width * 3
    for y in range(image.height):
        raw.append(0)
        start = y * row_bytes
        raw.extend(image.pixels[start : start + row_bytes])
    output.extend(_chunk(b"IDAT", zlib.compress(bytes(raw))))
    output.extend(_chunk(b"IEND", b""))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(bytes(output))


def resize_nearest(image: RgbImage, width: int, height: int) -> RgbImage:
    if width <= 0 or height <= 0:
        raise ValueError("target size must be positive")
    output = bytearray(width * height * 3)
    for y in range(height):
        source_y = min(image.height - 1, y * image.height // height)
        for x in range(width):
            source_x = min(image.width - 1, x * image.width // width)
            source_index = (source_y * image.width + source_x) * 3
            target_index = (y * width + x) * 3
            output[target_index : target_index + 3] = image.pixels[source_index : source_index + 3]
    return RgbImage(width=width, height=height, pixels=bytes(output))


def overlay(base: RgbImage, patch: RgbImage, *, x: int, y: int) -> RgbImage:
    output = bytearray(base.pixels)
    for patch_y in range(patch.height):
        target_y = y + patch_y
        if target_y < 0 or target_y >= base.height:
            continue
        for patch_x in range(patch.width):
            target_x = x + patch_x
            if target_x < 0 or target_x >= base.width:
                continue
            patch_index = (patch_y * patch.width + patch_x) * 3
            target_index = (target_y * base.width + target_x) * 3
            output[target_index : target_index + 3] = patch.pixels[patch_index : patch_index + 3]
    return RgbImage(width=base.width, height=base.height, pixels=bytes(output))


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(chunk_type)
    crc = binascii.crc32(data, crc)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc & 0xFFFFFFFF)

