from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from tryops.native_image_metrics import evaluate_with_native_image_metrics
from tryops.simple_image import RgbImage, read_png_rgb, resize_nearest


def mean_squared_error(reference: RgbImage, candidate: RgbImage) -> float:
    reference, candidate = _same_size(reference, candidate)
    if not reference.pixels:
        raise ValueError("images cannot be empty")
    total = 0.0
    for left, right in zip(reference.pixels, candidate.pixels, strict=True):
        diff = float(left) - float(right)
        total += diff * diff
    return round(total / len(reference.pixels), 6)


def psnr(reference: RgbImage, candidate: RgbImage) -> float:
    mse = mean_squared_error(reference, candidate)
    if mse == 0:
        return float("inf")
    return round(20.0 * math.log10(255.0 / math.sqrt(mse)), 6)


def global_ssim_luma(reference: RgbImage, candidate: RgbImage) -> float:
    """Compute a simple global luma SSIM approximation.

    This is not a replacement for windowed SSIM or LPIPS. It is a lightweight,
    deterministic structural metric for local smoke tests and baseline reports.
    """

    reference, candidate = _same_size(reference, candidate)
    left = _luma_values(reference)
    right = _luma_values(candidate)
    if not left:
        raise ValueError("images cannot be empty")

    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    var_left = sum((value - mean_left) ** 2 for value in left) / len(left)
    var_right = sum((value - mean_right) ** 2 for value in right) / len(right)
    covariance = sum(
        (left_value - mean_left) * (right_value - mean_right)
        for left_value, right_value in zip(left, right, strict=True)
    ) / len(left)

    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    numerator = (2 * mean_left * mean_right + c1) * (2 * covariance + c2)
    denominator = (mean_left**2 + mean_right**2 + c1) * (var_left + var_right + c2)
    if denominator == 0:
        return 1.0
    return round(max(-1.0, min(1.0, numerator / denominator)), 6)


def compare_png_files(reference_path: str | Path, candidate_path: str | Path) -> dict[str, float]:
    reference = read_png_rgb(reference_path)
    candidate = read_png_rgb(candidate_path)
    reference, candidate = _same_size(reference, candidate)
    dhash_distance = difference_hash_distance(reference, candidate)
    return {
        "mse": mean_squared_error(reference, candidate),
        "psnr": psnr(reference, candidate),
        "global_ssim_luma": global_ssim_luma(reference, candidate),
        "dhash_distance": float(dhash_distance),
        "dhash_similarity": round(1.0 - (dhash_distance / 64.0), 6),
    }


def compare_png_files_with_native(
    reference_path: str | Path,
    candidate_path: str | Path,
) -> dict[str, Any]:
    reference = read_png_rgb(reference_path)
    candidate = read_png_rgb(candidate_path)
    reference, candidate = _same_size(reference, candidate)
    metrics: dict[str, Any] = compare_images(reference, candidate)
    metrics["native"] = evaluate_with_native_image_metrics(reference, candidate)
    return metrics


def compare_images(reference: RgbImage, candidate: RgbImage) -> dict[str, float]:
    reference, candidate = _same_size(reference, candidate)
    dhash_distance = difference_hash_distance(reference, candidate)
    return {
        "mse": mean_squared_error(reference, candidate),
        "psnr": psnr(reference, candidate),
        "global_ssim_luma": global_ssim_luma(reference, candidate),
        "dhash_distance": float(dhash_distance),
        "dhash_similarity": round(1.0 - (dhash_distance / 64.0), 6),
        "edge_delta": edge_delta(reference, candidate),
    }


def difference_hash_distance(reference: RgbImage, candidate: RgbImage) -> int:
    reference_hash = _difference_hash(reference)
    candidate_hash = _difference_hash(candidate)
    return (reference_hash ^ candidate_hash).bit_count()


def edge_delta(reference: RgbImage, candidate: RgbImage) -> float:
    reference, candidate = _same_size(reference, candidate)
    if reference.width < 3 or reference.height < 3:
        return 0.0
    reference_luma = _luma_values(reference)
    candidate_luma = _luma_values(candidate)
    total = 0.0
    count = 0
    for y in range(1, reference.height - 1):
        for x in range(1, reference.width - 1):
            left_index = y * reference.width + x
            horizontal_left = abs(reference_luma[left_index + 1] - reference_luma[left_index - 1])
            vertical_left = abs(reference_luma[left_index + reference.width] - reference_luma[left_index - reference.width])
            horizontal_right = abs(candidate_luma[left_index + 1] - candidate_luma[left_index - 1])
            vertical_right = abs(candidate_luma[left_index + reference.width] - candidate_luma[left_index - reference.width])
            total += abs((horizontal_left + vertical_left) - (horizontal_right + vertical_right))
            count += 1
    return round(total / (count * 510.0), 6)


def _same_size(reference: RgbImage, candidate: RgbImage) -> tuple[RgbImage, RgbImage]:
    if reference.width == candidate.width and reference.height == candidate.height:
        return reference, candidate
    return reference, resize_nearest(candidate, reference.width, reference.height)


def _luma_values(image: RgbImage) -> list[float]:
    values: list[float] = []
    for index in range(0, len(image.pixels), 3):
        red = image.pixels[index]
        green = image.pixels[index + 1]
        blue = image.pixels[index + 2]
        values.append(0.299 * red + 0.587 * green + 0.114 * blue)
    return values


def _difference_hash(image: RgbImage) -> int:
    resized = resize_nearest(image, 9, 8)
    luma = _luma_values(resized)
    value = 0
    bit = 0
    for y in range(8):
        for x in range(8):
            left = luma[y * 9 + x]
            right = luma[y * 9 + x + 1]
            if left > right:
                value |= 1 << bit
            bit += 1
    return value
