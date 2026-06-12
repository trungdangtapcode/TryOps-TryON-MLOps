from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ALLOWED_ARTIFACT_ROOTS = (
    Path("artifacts/eval"),
    Path("artifacts/demo"),
    Path("artifacts/deployments"),
    Path("artifacts/runtime"),
    Path("reports/generated"),
)

MEDIA_TYPES = {
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".md": "text/markdown; charset=utf-8",
}


def resolve_artifact_path(requested_path: str, root: Path | None = None) -> Path:
    if not requested_path.strip():
        raise ValueError("artifact path is required")
    candidate = Path(requested_path)
    if candidate.is_absolute():
        raise ValueError("absolute artifact paths are not allowed")
    if ".." in candidate.parts:
        raise ValueError("artifact path traversal is not allowed")
    workspace = (root or Path.cwd()).resolve()
    resolved = (workspace / candidate).resolve()
    for allowed_root in ALLOWED_ARTIFACT_ROOTS:
        allowed = (workspace / allowed_root).resolve()
        if resolved == allowed or allowed in resolved.parents:
            if not resolved.is_file():
                raise ValueError("artifact path does not resolve to a file")
            return resolved
    raise ValueError("artifact path is outside allowed roots")


def artifact_media_type(path: Path) -> str:
    media_type = MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ValueError(f"unsupported artifact type: {path.suffix}")
    return media_type


def load_json_artifact(requested_path: str, root: Path | None = None) -> dict[str, Any]:
    path = resolve_artifact_path(requested_path, root=root)
    if artifact_media_type(path) != "application/json":
        raise ValueError("artifact is not JSON")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("artifact JSON root must be an object")
    return payload


def with_artifact_urls(payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    for key in ("person_image_path", "garment_image_path"):
        if isinstance(enriched.get(key), str):
            enriched[f"{key}_url"] = artifact_url(str(enriched[key]))
    runs = []
    for run in payload.get("runs", []):
        if not isinstance(run, dict):
            continue
        run_copy = dict(run)
        output_path = run_copy.get("output_path")
        report_path = run_copy.get("report_path")
        if isinstance(output_path, str):
            run_copy["output_url"] = artifact_url(output_path)
        if isinstance(report_path, str):
            run_copy["report_url"] = artifact_url(report_path)
        runs.append(run_copy)
    enriched["runs"] = runs
    return enriched


def artifact_url(path: str) -> str:
    return f"/api/artifacts/file?{urlencode({'path': path})}"
