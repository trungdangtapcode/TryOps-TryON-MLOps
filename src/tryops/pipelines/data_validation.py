from __future__ import annotations

from typing import Any


REQUIRED_IMAGE_FIELDS = {"id", "path", "split", "checksum", "license"}
ALLOWED_SPLITS = {"train", "validation", "test", "demo", "calibration"}


def validate_dataset_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate a dataset manifest without reading the image bytes."""

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return {"passed": False, "errors": ["manifest.entries must be a list"], "stats": {}}

    errors: list[str] = []
    split_counts: dict[str, int] = {}
    seen_ids: set[str] = set()
    seen_checksums: set[str] = set()

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry {index} must be an object")
            continue

        missing = sorted(REQUIRED_IMAGE_FIELDS - set(entry))
        if missing:
            errors.append(f"entry {index} missing fields: {', '.join(missing)}")

        item_id = str(entry.get("id", ""))
        checksum = str(entry.get("checksum", ""))
        split = str(entry.get("split", ""))

        if item_id in seen_ids:
            errors.append(f"duplicate id '{item_id}'")
        if item_id:
            seen_ids.add(item_id)

        if checksum in seen_checksums:
            errors.append(f"duplicate checksum '{checksum}'")
        if checksum:
            seen_checksums.add(checksum)

        if split and split not in ALLOWED_SPLITS:
            errors.append(f"entry {index} has invalid split '{split}'")
        if split:
            split_counts[split] = split_counts.get(split, 0) + 1

    stats = {
        "entry_count": len(entries),
        "split_counts": split_counts,
        "unique_ids": len(seen_ids),
        "unique_checksums": len(seen_checksums),
    }
    return {"passed": not errors, "errors": errors, "stats": stats}

