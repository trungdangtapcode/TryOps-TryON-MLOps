from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from tryops import db
from tryops.runtime_artifacts import artifact_id_from_ref, storage_from_env


def main() -> None:
    base_url = os.getenv("TRYOPS_STACK_GATEWAY_URL", "http://127.0.0.1:18081").rstrip("/")
    api_key = os.getenv("TRYOPS_SMOKE_API_KEY", "tryops-admin-demo-key")
    _wait_for_ready(base_url)

    person = _upload_png(base_url, api_key, role="person", path=Path("artifacts/demo/vton/person.png"))
    garment = _upload_png(base_url, api_key, role="garment", path=Path("artifacts/demo/vton/garment.png"))
    person_path = person["data"]["path"]
    garment_path = garment["data"]["path"]
    if not str(person_path).startswith("artifact:") or not str(garment_path).startswith("artifact:"):
        raise SystemExit(f"upload did not return MinIO artifact refs: {person_path}, {garment_path}")

    payload = {
        "api_key": api_key,
        "person_image_path": person_path,
        "garment_image_path": garment_path,
        "output_image_path": "artifacts/runtime/vton/smoke-output.png",
        "model_alias": "baseline",
        "quota_plan": "free",
        "user_id": "runtime-artifact-smoke",
        "timeout_ms": 300000,
    }
    response = _post_json(f"{base_url}/api/vton/infer", payload)
    if response.get("status") != "completed":
        raise SystemExit(f"VTON smoke failed: {json.dumps(response, indent=2)}")
    output_ref = str(response.get("report", {}).get("output", {}).get("path") or "")
    artifact_id = artifact_id_from_ref(output_ref)
    if not artifact_id:
        raise SystemExit(f"VTON output is not an artifact ref: {output_ref}")

    conn = db.connect()
    try:
        artifact = db.get_artifact_object(conn, artifact_id)
    finally:
        conn.close()
    if not artifact or artifact.get("backend") != "minio":
        raise SystemExit(f"artifact row is not MinIO-backed: {artifact}")

    storage = storage_from_env()
    if storage is None:
        raise SystemExit("MinIO runtime artifact storage is not configured for smoke verification")
    storage.stat(object_key=str(artifact["object_key"]))

    query = urllib.parse.urlencode({"path": output_ref, "api_key": api_key})
    downloaded = _get_bytes(f"{base_url}/api/artifacts/file?{query}")
    if not downloaded.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit("artifact API did not return a PNG image")
    print(
        "Runtime artifact MinIO smoke passed: "
        f"upload_refs=({person_path}, {garment_path}) output_ref={output_ref}"
    )


def _upload_png(base_url: str, api_key: str, *, role: str, path: Path) -> dict[str, Any]:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return _post_json(
        f"{base_url}/api/vton/upload",
        {
            "api_key": api_key,
            "role": role,
            "filename": path.name,
            "data_url": f"data:image/png;base64,{encoded}",
        },
    )


def _wait_for_ready(base_url: str) -> None:
    last_error = ""
    for _ in range(60):
        try:
            ready = _get_json(f"{base_url}/api/ready")
            if ready.get("status") == "ready":
                return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise SystemExit(f"TryOps gateway was not ready: {last_error}")


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    return _read_json(request)


def _get_json(url: str) -> dict[str, Any]:
    return _read_json(urllib.request.Request(url, method="GET"))


def _get_bytes(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc


def _read_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("expected JSON object")
    return payload


if __name__ == "__main__":
    main()
