from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from tryops.pipelines.data_ingestion import read_image_metadata, sha256_file, validate_image_file


def build_vton_preflight(
    *,
    person_image_path: str | Path,
    garment_image_path: str | Path,
    cache_dir: str | Path,
    max_size_bytes: int = 10 * 1024 * 1024,
) -> dict[str, Any]:
    """Validate and normalize VTON request metadata before model inference."""

    started = perf_counter()
    person_path = Path(person_image_path)
    garment_path = Path(garment_image_path)
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    person_validation = validate_image_file(person_path, max_size_bytes=max_size_bytes)
    garment_validation = validate_image_file(garment_path, max_size_bytes=max_size_bytes)
    errors = [
        f"person image: {error}" for error in person_validation["errors"]
    ] + [
        f"garment image: {error}" for error in garment_validation["errors"]
    ]
    cache_key = _cache_key(person_path, garment_path) if not errors else None

    report = {
        "schema_version": "tryops.vton_preflight.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "passed": not errors,
        "errors": errors,
        "cache_key": cache_key,
        "person": _image_record(person_path, person_validation),
        "garment": _image_record(garment_path, garment_validation),
        "latency_ms": round((perf_counter() - started) * 1000.0, 3),
    }

    if cache_key is not None:
        (cache_path / f"{cache_key}.json").write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return report


def _image_record(path: Path, validation: dict[str, Any]) -> dict[str, Any]:
    record = {
        "path": str(path),
        "passed": validation["passed"],
        "format": validation["format"],
        "width": validation["width"],
        "height": validation["height"],
        "color_mode": validation["color_mode"],
        "size_bytes": validation["size_bytes"],
    }
    if validation["passed"]:
        record["checksum"] = sha256_file(path)
        record["metadata"] = read_image_metadata(path)
    return record


def _cache_key(person_path: Path, garment_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(sha256_file(person_path).encode("utf-8"))
    digest.update(b"\n")
    digest.update(sha256_file(garment_path).encode("utf-8"))
    return digest.hexdigest()[:32]

