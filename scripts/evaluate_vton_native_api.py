#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient  # noqa: E402

from tryops import db  # noqa: E402
from tryops.api import create_app  # noqa: E402
from tryops.pipelines.data_ingestion import sha256_file  # noqa: E402
from tryops.simple_image import RgbImage, solid_rgb, write_png_rgb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify native C++ VTON evidence through the API path.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/vton_native_api/vton_native_api_report.json"))
    parser.add_argument("--work-dir", type=Path, default=Path("artifacts/eval/vton_native_api"))
    args = parser.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    person_path = args.work_dir / "person.png"
    garment_path = args.work_dir / "garment.png"
    output_path = args.work_dir / "api_output.png"
    write_png_rgb(person_path, _person_image())
    write_png_rgb(garment_path, _garment_image())

    request_id = "req-vton-native-api-sample"
    response = TestClient(create_app()).post(
        "/v1/vton/infer",
        json={
            "request_id": request_id,
            "person_image_path": str(person_path),
            "garment_image_path": str(garment_path),
            "output_image_path": str(output_path),
            "cache_dir": str(args.work_dir / "cache"),
            "timeout_ms": 5000,
            "user_id": "native-vton-sample",
            "quota_plan": "enterprise",
        },
    )
    body = response.json()
    native_vton = body.get("native_vton", {})
    preprocessing = native_vton.get("preprocessing", {})
    image_metrics = native_vton.get("image_metrics", {})
    db_quality = _latest_quality_for_request(request_id)
    sidecar = _load_sidecar(output_path)

    checks = [
        _check("api_completed", response.status_code == 200 and body.get("status") == "completed"),
        _check("native_preprocess_person_available", bool(preprocessing.get("person", {}).get("available"))),
        _check("native_preprocess_garment_available", bool(preprocessing.get("garment", {}).get("available"))),
        _check("native_image_metrics_available", bool(image_metrics.get("available"))),
        _check("native_quality_score_present", isinstance(native_vton.get("quality_score"), (int, float))),
        _check("sidecar_has_native_execution", sidecar.get("native_execution", {}).get("schema_version") == "tryops.native_vton_execution.v1"),
        _check("request_detail_quality_persisted", isinstance(db_quality, (int, float))),
    ]
    report = {
        "schema_version": "tryops.vton_native_api.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "passed": all(check["passed"] for check in checks),
        "request_id": request_id,
        "artifacts": {
            "person": str(person_path),
            "garment": str(garment_path),
            "output": str(output_path),
            "sidecar": str(output_path.with_suffix(".png.json")),
        },
        "checks": checks,
        "native_vton": native_vton,
        "db_quality": db_quality,
        "checksums": {
            "person": sha256_file(person_path),
            "garment": sha256_file(garment_path),
            "output": sha256_file(output_path),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


def _latest_quality_for_request(request_id: str) -> float | None:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT quality FROM requests WHERE request_id=? ORDER BY created_at DESC LIMIT 1",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return row["quality"]
    finally:
        conn.close()


def _load_sidecar(output_path: Path) -> dict[str, Any]:
    sidecar_path = output_path.with_suffix(".png.json")
    if not sidecar_path.exists():
        return {}
    return json.loads(sidecar_path.read_text(encoding="utf-8"))


def _check(name: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "passed": passed}


def _person_image() -> RgbImage:
    image = bytearray(solid_rgb(180, 240, (235, 238, 242)).pixels)
    width = 180
    for y in range(36, 220):
        for x in range(54, 126):
            index = (y * width + x) * 3
            image[index : index + 3] = bytes([210, 180, 150])
    for y in range(70, 220):
        for x in range(50, 130):
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
