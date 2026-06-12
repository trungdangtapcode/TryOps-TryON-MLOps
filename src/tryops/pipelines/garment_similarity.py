from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path
from typing import Any

from tryops.pipelines.image_metrics import compare_images
from tryops.simple_image import RgbImage, read_png_rgb, resize_nearest


DEFAULT_GARMENT_TEXT_PROMPTS = [
    "a photo of the target garment",
    "a clean product photo of the same clothing item",
    "a virtual try-on output preserving the source garment",
]


def evaluate_garment_similarity(
    *,
    garment_image_path: str | Path,
    output_image_path: str | Path,
    overlay: dict[str, int] | None = None,
    text_prompts: list[str] | None = None,
    enable_openclip: bool | None = None,
    enable_clip: bool | None = None,
    clip_backend: str | None = None,
    openclip_model: str = "ViT-B-32",
    openclip_pretrained: str = "laion2b_s34b_b79k",
    transformers_clip_model: str = "openai/clip-vit-base-patch32",
) -> dict[str, Any]:
    """Evaluate whether a generated VTON output preserves the source garment.

    The OpenCLIP path is optional because it needs neural dependencies and a local
    or downloadable checkpoint. The proxy path is deterministic and always runs.
    """

    garment = read_png_rgb(garment_image_path)
    output = read_png_rgb(output_image_path)
    output_patch = crop_rgb(output, overlay) if overlay is not None else resize_nearest(output, garment.width, garment.height)
    reference = resize_nearest(garment, output_patch.width, output_patch.height)

    prompts = text_prompts or DEFAULT_GARMENT_TEXT_PROMPTS
    return {
        "schema_version": "tryops.garment_similarity.v1",
        "garment_image_path": str(garment_image_path),
        "output_image_path": str(output_image_path),
        "overlay": dict(overlay) if overlay is not None else None,
        "proxy": proxy_garment_image_similarity(reference, output_patch),
        "clip": evaluate_clip_similarity(
            reference=reference,
            candidate=output_patch,
            text_prompts=prompts,
            enabled=_clip_enabled(enable_clip, enable_openclip),
            backend=clip_backend or os.environ.get("TRYOPS_CLIP_BACKEND", "auto"),
            model_name=openclip_model,
            pretrained=openclip_pretrained,
            transformers_model=transformers_clip_model,
        ),
    }


def proxy_garment_image_similarity(reference: RgbImage, candidate: RgbImage) -> dict[str, Any]:
    reference, candidate = _same_size(reference, candidate)
    raw_metrics = compare_images(reference, candidate)
    structural_similarity = max(0.0, min(1.0, (raw_metrics["global_ssim_luma"] + 1.0) / 2.0))
    edge_similarity = max(0.0, min(1.0, 1.0 - raw_metrics["edge_delta"]))
    histogram_similarity = rgb_histogram_intersection(reference, candidate)
    score = (
        0.45 * raw_metrics["dhash_similarity"]
        + 0.35 * structural_similarity
        + 0.15 * histogram_similarity
        + 0.05 * edge_similarity
    )
    return {
        "method": "garment_patch_structural_proxy",
        "score": round(score, 6),
        "dhash_similarity": raw_metrics["dhash_similarity"],
        "structural_similarity": round(structural_similarity, 6),
        "histogram_similarity": histogram_similarity,
        "edge_similarity": round(edge_similarity, 6),
        "metrics": _json_safe_metrics(raw_metrics),
        "limitations": [
            "This is not CLIP or OpenCLIP.",
            "It compares the generated output patch against the source garment for local smoke testing.",
        ],
    }


def evaluate_clip_similarity(
    *,
    reference: RgbImage,
    candidate: RgbImage,
    text_prompts: list[str],
    enabled: bool,
    backend: str,
    model_name: str,
    pretrained: str,
    transformers_model: str,
) -> dict[str, Any]:
    dependencies = {
        "torch": importlib.util.find_spec("torch") is not None,
        "open_clip": importlib.util.find_spec("open_clip") is not None,
        "transformers": importlib.util.find_spec("transformers") is not None,
        "PIL": importlib.util.find_spec("PIL") is not None,
    }
    normalized_backend = backend.strip().lower().replace("-", "_")
    if not enabled:
        return {
            "available": False,
            "enabled": False,
            "backend": normalized_backend,
            "model_name": model_name,
            "pretrained": pretrained,
            "transformers_model": transformers_model,
            "dependencies": dependencies,
            "reason": "set TRYOPS_ENABLE_CLIP=1 or pass --enable-clip to run neural CLIP similarity",
        }

    if normalized_backend in {"auto", "open_clip", "openclip"} and dependencies["open_clip"]:
        try:
            return _run_openclip_similarity(
                reference=reference,
                candidate=candidate,
                text_prompts=text_prompts,
                model_name=model_name,
                pretrained=pretrained,
            )
        except Exception as error:  # pragma: no cover - depends on optional neural runtime.
            if normalized_backend not in {"auto"}:
                return {
                    "available": False,
                    "enabled": True,
                    "backend": "open_clip",
                    "model_name": model_name,
                    "pretrained": pretrained,
                    "dependencies": dependencies,
                    "reason": str(error),
                }

    if normalized_backend in {"auto", "transformers", "transformers_clip", "hf_clip"}:
        required = {"torch": dependencies["torch"], "transformers": dependencies["transformers"], "PIL": dependencies["PIL"]}
        if all(required.values()):
            try:
                return _run_transformers_clip_similarity(
                    reference=reference,
                    candidate=candidate,
                    text_prompts=text_prompts,
                    model_id=transformers_model,
                )
            except Exception as error:  # pragma: no cover - depends on optional neural runtime/model.
                return {
                    "available": False,
                    "enabled": True,
                    "backend": "transformers_clip",
                    "model_name": transformers_model,
                    "dependencies": dependencies,
                    "reason": str(error),
                }
        missing = [name for name, present in required.items() if not present]
        return {
            "available": False,
            "enabled": True,
            "backend": "transformers_clip",
            "model_name": transformers_model,
            "dependencies": dependencies,
            "reason": f"missing dependencies: {', '.join(missing)}",
        }

    return {
        "available": False,
        "enabled": True,
        "backend": normalized_backend,
        "model_name": model_name,
        "pretrained": pretrained,
        "transformers_model": transformers_model,
        "dependencies": dependencies,
        "reason": f"unsupported CLIP backend: {backend}",
    }


def crop_rgb(image: RgbImage, overlay: dict[str, int]) -> RgbImage:
    x = int(overlay["x"])
    y = int(overlay["y"])
    width = int(overlay["width"])
    height = int(overlay["height"])
    if width <= 0 or height <= 0:
        raise ValueError("overlay width and height must be positive")
    if x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError("overlay region is outside image bounds")

    pixels = bytearray(width * height * 3)
    for row in range(height):
        source_start = ((y + row) * image.width + x) * 3
        source_end = source_start + width * 3
        target_start = row * width * 3
        pixels[target_start : target_start + width * 3] = image.pixels[source_start:source_end]
    return RgbImage(width=width, height=height, pixels=bytes(pixels))


def rgb_histogram_intersection(reference: RgbImage, candidate: RgbImage, bins: int = 8) -> float:
    reference, candidate = _same_size(reference, candidate)
    left = _rgb_histogram(reference, bins)
    right = _rgb_histogram(candidate, bins)
    return round(sum(min(left_value, right_value) for left_value, right_value in zip(left, right, strict=True)), 6)


def _rgb_histogram(image: RgbImage, bins: int) -> list[float]:
    if bins <= 0 or 256 % bins != 0:
        raise ValueError("bins must be a positive divisor of 256")
    histogram = [0.0] * (bins * 3)
    bucket_width = 256 // bins
    pixel_count = image.width * image.height
    for index in range(0, len(image.pixels), 3):
        for channel in range(3):
            value = image.pixels[index + channel]
            bucket = min(bins - 1, value // bucket_width)
            histogram[channel * bins + bucket] += 1.0
    normalizer = max(1, pixel_count * 3)
    return [value / normalizer for value in histogram]


def _same_size(reference: RgbImage, candidate: RgbImage) -> tuple[RgbImage, RgbImage]:
    if reference.width == candidate.width and reference.height == candidate.height:
        return reference, candidate
    return reference, resize_nearest(candidate, reference.width, reference.height)


def _json_safe_metrics(metrics: dict[str, float]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, float) and not math.isfinite(value):
            safe[key] = None
            safe[f"{key}_is_infinite"] = math.isinf(value)
        else:
            safe[key] = value
    return safe


def _clip_enabled(value: bool | None, legacy_openclip_value: bool | None = None) -> bool:
    if value is not None:
        return value
    if legacy_openclip_value is not None:
        return legacy_openclip_value
    if os.environ.get("TRYOPS_ENABLE_CLIP", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return os.environ.get("TRYOPS_ENABLE_OPENCLIP", "").strip().lower() in {"1", "true", "yes", "on"}


def _run_openclip_similarity(
    *,
    reference: RgbImage,
    candidate: RgbImage,
    text_prompts: list[str],
    model_name: str,
    pretrained: str,
) -> dict[str, Any]:
    import open_clip  # type: ignore[import-not-found]
    import torch

    device = os.environ.get("TRYOPS_OPENCLIP_DEVICE")
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    tokenizer = open_clip.get_tokenizer(model_name)
    model = model.to(device)
    model.eval()

    with torch.no_grad():
        reference_input = preprocess(_to_pil(reference)).unsqueeze(0).to(device)
        candidate_input = preprocess(_to_pil(candidate)).unsqueeze(0).to(device)
        reference_features = model.encode_image(reference_input)
        candidate_features = model.encode_image(candidate_input)
        reference_features = reference_features / reference_features.norm(dim=-1, keepdim=True)
        candidate_features = candidate_features / candidate_features.norm(dim=-1, keepdim=True)
        image_similarity = float((reference_features @ candidate_features.T).item())

        text_results: list[dict[str, Any]] = []
        if text_prompts:
            text_tokens = tokenizer(text_prompts).to(device)
            text_features = model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            similarities = (candidate_features @ text_features.T).squeeze(0).detach().cpu().tolist()
            text_results = [
                {"prompt": prompt, "similarity": round(float(score), 6)}
                for prompt, score in zip(text_prompts, similarities, strict=True)
            ]

    best_text = max(text_results, key=lambda item: item["similarity"]) if text_results else None
    return {
        "available": True,
        "enabled": True,
        "backend": "open_clip",
        "model_name": model_name,
        "pretrained": pretrained,
        "device": device,
        "image_similarity": round(image_similarity, 6),
        "text_prompts": text_results,
        "best_text_prompt": best_text,
    }


def _run_transformers_clip_similarity(
    *,
    reference: RgbImage,
    candidate: RgbImage,
    text_prompts: list[str],
    model_id: str,
) -> dict[str, Any]:
    import torch
    from transformers import CLIPModel, CLIPProcessor

    device = os.environ.get("TRYOPS_CLIP_DEVICE")
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = CLIPModel.from_pretrained(model_id).to(device)
    processor = CLIPProcessor.from_pretrained(model_id)
    model.eval()

    with torch.no_grad():
        image_inputs = processor(
            images=[_to_pil(reference), _to_pil(candidate)],
            return_tensors="pt",
        )
        image_inputs = {key: value.to(device) for key, value in image_inputs.items()}
        image_features = model.get_image_features(**image_inputs)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        image_similarity = float((image_features[0:1] @ image_features[1:2].T).item())

        text_results: list[dict[str, Any]] = []
        if text_prompts:
            text_inputs = processor(
                text=text_prompts,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            text_inputs = {key: value.to(device) for key, value in text_inputs.items()}
            candidate_features = image_features[1:2]
            text_features = model.get_text_features(**text_inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            similarities = (candidate_features @ text_features.T).squeeze(0).detach().cpu().tolist()
            text_results = [
                {"prompt": prompt, "similarity": round(float(score), 6)}
                for prompt, score in zip(text_prompts, similarities, strict=True)
            ]

    best_text = max(text_results, key=lambda item: item["similarity"]) if text_results else None
    return {
        "available": True,
        "enabled": True,
        "backend": "transformers_clip",
        "model_name": model_id,
        "device": device,
        "image_similarity": round(image_similarity, 6),
        "text_prompts": text_results,
        "best_text_prompt": best_text,
        "model_source": "huggingface_transformers",
    }


def _to_pil(image: RgbImage) -> Any:
    from PIL import Image

    return Image.frombytes("RGB", (image.width, image.height), image.pixels)
