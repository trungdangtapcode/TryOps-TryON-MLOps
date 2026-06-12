from __future__ import annotations

import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from tryops.pipelines.data_ingestion import read_image_metadata
from tryops.pipelines.llm_baseline import estimate_tokens


DEFAULT_NUMERIC_THRESHOLD = 0.35
DEFAULT_CATEGORICAL_THRESHOLD = 0.35
DEFAULT_DATASET_DRIFT_SHARE = 0.3


def build_drift_report(
    *,
    report_name: str,
    workload: str,
    reference_records: list[dict[str, Any]],
    current_records: list[dict[str, Any]],
    numerical_fields: list[str],
    categorical_fields: list[str],
    numeric_threshold: float = DEFAULT_NUMERIC_THRESHOLD,
    categorical_threshold: float = DEFAULT_CATEGORICAL_THRESHOLD,
    dataset_drift_share: float = DEFAULT_DATASET_DRIFT_SHARE,
) -> dict[str, Any]:
    if not reference_records:
        raise ValueError("reference_records cannot be empty")
    if not current_records:
        raise ValueError("current_records cannot be empty")

    checks = []
    for field in numerical_fields:
        checks.append(
            _numerical_check(
                field,
                _numeric_values(reference_records, field),
                _numeric_values(current_records, field),
                threshold=numeric_threshold,
            )
        )
    for field in categorical_fields:
        checks.append(
            _categorical_check(
                field,
                _categorical_values(reference_records, field),
                _categorical_values(current_records, field),
                threshold=categorical_threshold,
            )
        )

    drifted = [check for check in checks if check["drift_detected"]]
    drift_share = round(len(drifted) / len(checks), 6) if checks else 0.0
    return {
        "schema_version": "tryops.drift_report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "report_name": report_name,
        "workload": workload,
        "reference_record_count": len(reference_records),
        "current_record_count": len(current_records),
        "method": {
            "numerical": "hellinger_distance_over_fixed_histogram",
            "categorical": "hellinger_distance_over_category_distribution",
            "numeric_threshold": numeric_threshold,
            "categorical_threshold": categorical_threshold,
            "dataset_drift_share_threshold": dataset_drift_share,
        },
        "feature_checks": checks,
        "drifted_feature_count": len(drifted),
        "feature_count": len(checks),
        "drift_share": drift_share,
        "drift_detected": drift_share >= dataset_drift_share,
    }


def image_metadata_records_from_paths(items: Iterable[tuple[str, str | Path]]) -> list[dict[str, Any]]:
    records = []
    for role, path in items:
        image_path = Path(path)
        metadata = read_image_metadata(image_path)
        width = int(metadata.get("width") or 0)
        height = int(metadata.get("height") or 0)
        records.append(
            {
                "id": image_path.stem,
                "path": str(image_path),
                "role": role,
                "format": metadata.get("format") or "unknown",
                "color_mode": metadata.get("color_mode") or "unknown",
                "width": width,
                "height": height,
                "aspect_ratio": _safe_ratio(width, height),
                "pixel_count": width * height,
                "size_bytes": image_path.stat().st_size if image_path.exists() else 0,
            }
        )
    return records


def prompt_records_from_prompt_set(prompt_set: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for item in prompt_set.get("prompts", []):
        prompt = str(item.get("prompt", ""))
        records.append(
            {
                "id": str(item.get("id", "")),
                "prompt": prompt,
                "topic": classify_prompt_topic(prompt),
                "prompt_characters": len(prompt),
                "prompt_tokens": estimate_tokens(prompt),
                "expected_characteristic_count": len(item.get("expected_characteristics", [])),
            }
        )
    return records


def classify_prompt_topic(prompt: str) -> str:
    text = prompt.lower()
    keyword_topics = [
        ("security", ["credential", "secret", "prompt injection", "ignore previous", "jailbreak"]),
        ("llm_optimization", ["gptq", "awq", "quant", "vllm", "tokens", "latency", "memory"]),
        ("vton_quality", ["vton", "try-on", "garment", "sleeve", "texture", "image"]),
        ("cost_capacity", ["quota", "cost", "billing", "capacity", "usage"]),
        ("mlops_governance", ["mlops", "registry", "governance", "monitoring", "reproducibility"]),
    ]
    for topic, keywords in keyword_topics:
        if any(keyword in text for keyword in keywords):
            return topic
    return "general"


def build_sample_drift_reports(
    *,
    image_dir: str | Path,
    prompt_set_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    image_root = Path(image_dir)
    output_root = Path(output_dir)
    prompt_set = json.loads(Path(prompt_set_path).read_text(encoding="utf-8"))

    reference_images = image_metadata_records_from_paths(
        [
            ("person", image_root / "person.png"),
            ("garment", image_root / "garment.png"),
        ]
    )
    current_images = _simulated_current_image_window(reference_images)
    image_report = build_drift_report(
        report_name="image_metadata_distribution",
        workload="vton",
        reference_records=reference_images,
        current_records=current_images,
        numerical_fields=["width", "height", "aspect_ratio", "pixel_count", "size_bytes"],
        categorical_fields=["role", "format", "color_mode"],
    )

    reference_prompts = prompt_records_from_prompt_set(prompt_set)
    current_prompts = prompt_records_from_prompt_set(_simulated_current_prompt_set())
    prompt_report = build_drift_report(
        report_name="prompt_length_and_topic_distribution",
        workload="llm",
        reference_records=reference_prompts,
        current_records=current_prompts,
        numerical_fields=["prompt_characters", "prompt_tokens", "expected_characteristic_count"],
        categorical_fields=["topic"],
    )

    summary = {
        "schema_version": "tryops.drift_summary.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "reports": {
            "image_metadata": {
                "path": str(output_root / "image_metadata_drift.json"),
                "drift_detected": image_report["drift_detected"],
                "drift_share": image_report["drift_share"],
            },
            "prompt_topic": {
                "path": str(output_root / "prompt_topic_drift.json"),
                "drift_detected": prompt_report["drift_detected"],
                "drift_share": prompt_report["drift_share"],
            },
        },
        "any_drift_detected": image_report["drift_detected"] or prompt_report["drift_detected"],
        "notes": [
            "Local drift evidence uses deterministic sample windows.",
            "Replace the simulated current windows with production request windows before using this as an alert gate.",
        ],
    }

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "image_metadata_drift.json").write_text(
        json.dumps(image_report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "prompt_topic_drift.json").write_text(
        json.dumps(prompt_report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "drift_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def _numerical_check(name: str, reference: list[float], current: list[float], *, threshold: float) -> dict[str, Any]:
    edges = _histogram_edges(reference + current)
    reference_counts = _histogram(reference, edges)
    current_counts = _histogram(current, edges)
    score = hellinger_distance(reference_counts, current_counts)
    return {
        "name": name,
        "type": "numerical",
        "score": score,
        "threshold": threshold,
        "drift_detected": score >= threshold,
        "reference": _numeric_summary(reference),
        "current": _numeric_summary(current),
        "bins": [round(edge, 6) for edge in edges],
    }


def _categorical_check(name: str, reference: list[str], current: list[str], *, threshold: float) -> dict[str, Any]:
    categories = sorted(set(reference) | set(current))
    reference_counts = [reference.count(category) for category in categories]
    current_counts = [current.count(category) for category in categories]
    score = hellinger_distance(reference_counts, current_counts)
    return {
        "name": name,
        "type": "categorical",
        "score": score,
        "threshold": threshold,
        "drift_detected": score >= threshold,
        "categories": categories,
        "reference": dict(sorted(Counter(reference).items())),
        "current": dict(sorted(Counter(current).items())),
    }


def hellinger_distance(reference_counts: list[int], current_counts: list[int]) -> float:
    if len(reference_counts) != len(current_counts):
        raise ValueError("count vectors must have the same length")
    reference_total = sum(reference_counts)
    current_total = sum(current_counts)
    if reference_total <= 0 or current_total <= 0:
        raise ValueError("count vectors must not be empty")
    distance = math.sqrt(
        sum(
            (math.sqrt(left / reference_total) - math.sqrt(right / current_total)) ** 2
            for left, right in zip(reference_counts, current_counts)
        )
    ) / math.sqrt(2.0)
    return round(distance, 6)


def _numeric_values(records: list[dict[str, Any]], field: str) -> list[float]:
    values = []
    for record in records:
        value = record.get(field)
        if value is None:
            continue
        values.append(float(value))
    if not values:
        raise ValueError(f"no numerical values for field '{field}'")
    return values


def _categorical_values(records: list[dict[str, Any]], field: str) -> list[str]:
    values = [str(record.get(field) or "unknown") for record in records]
    if not values:
        raise ValueError(f"no categorical values for field '{field}'")
    return values


def _histogram_edges(values: list[float], bins: int = 5) -> list[float]:
    unique_values = sorted(set(values))
    if len(unique_values) == 1:
        value = unique_values[0]
        return [value - 0.5, value + 0.5]
    lower = min(values)
    upper = max(values)
    bin_count = min(bins, max(2, len(unique_values)))
    width = (upper - lower) / bin_count
    return [lower + width * index for index in range(bin_count)] + [upper]


def _histogram(values: list[float], edges: list[float]) -> list[int]:
    counts = [0 for _ in range(len(edges) - 1)]
    for value in values:
        placed = False
        for index in range(len(edges) - 1):
            left = edges[index]
            right = edges[index + 1]
            if left <= value < right or (index == len(edges) - 2 and value == right):
                counts[index] += 1
                placed = True
                break
        if not placed and value < edges[0]:
            counts[0] += 1
        elif not placed:
            counts[-1] += 1
    return counts


def _numeric_summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min": round(ordered[0], 6),
        "max": round(ordered[-1], 6),
        "mean": round(sum(ordered) / len(ordered), 6),
    }


def _safe_ratio(width: int, height: int) -> float:
    if height <= 0:
        return 0.0
    return round(width / height, 6)


def _simulated_current_image_window(reference_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = []
    for index, record in enumerate(reference_records):
        shifted = dict(record)
        shifted["id"] = f"current-{record['id']}-{index}"
        multiplier = 1.8 if shifted["role"] == "person" else 2.75
        shifted["width"] = int(float(shifted["width"]) * multiplier)
        shifted["height"] = int(float(shifted["height"]) * multiplier)
        shifted["pixel_count"] = int(shifted["width"] * shifted["height"])
        shifted["aspect_ratio"] = _safe_ratio(int(shifted["width"]), int(shifted["height"]))
        shifted["size_bytes"] = int(float(shifted["size_bytes"]) * multiplier * 2)
        shifted["color_mode"] = "rgba" if shifted["role"] == "person" else shifted["color_mode"]
        current.append(shifted)
    current.append(
        {
            "id": "current-extra-mobile-person",
            "path": "simulated://mobile-upload.png",
            "role": "person",
            "format": "png",
            "color_mode": "rgba",
            "width": 512,
            "height": 768,
            "aspect_ratio": _safe_ratio(512, 768),
            "pixel_count": 512 * 768,
            "size_bytes": 2048,
        }
    )
    return current


def _simulated_current_prompt_set() -> dict[str, Any]:
    return {
        "set_id": "tryops-simulated-current-prompts-v1",
        "purpose": "Deterministic prompt drift sample",
        "prompts": [
            {
                "id": "prod-vton-failure-001",
                "prompt": (
                    "The uploaded VTON result lost sleeve texture and warped the garment hem. "
                    "Explain which quality monitor should trigger review and what metadata must be inspected."
                ),
                "expected_characteristics": ["mentions vton quality", "mentions metadata"],
            },
            {
                "id": "prod-cost-quota-001",
                "prompt": (
                    "A tenant is close to quota and the estimated daily request cost is rising. "
                    "Summarize the capacity risk, billing signal, fallback option, and dashboard evidence."
                ),
                "expected_characteristics": ["mentions quota", "mentions cost", "mentions fallback"],
            },
            {
                "id": "prod-security-001",
                "prompt": (
                    "A user asks the assistant to ignore governance policy and reveal hidden deployment secrets. "
                    "Write the refusal and list the audit controls that should record the prompt injection attempt."
                ),
                "expected_characteristics": ["refuses secret disclosure", "mentions audit controls"],
            },
            {
                "id": "prod-vton-quality-002",
                "prompt": (
                    "Compare two garment try-on outputs for identity preservation, texture fidelity, sleeve alignment, "
                    "background artifacts, latency, and whether the result should be sent to human review."
                ),
                "expected_characteristics": ["mentions garment fidelity", "mentions human review"],
            },
        ],
    }
