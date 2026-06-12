#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.api import create_app  # noqa: E402
from tryops.jobs import reset_job_queue  # noqa: E402
from tryops.quota import reset_quota_usage  # noqa: E402
from tryops.simple_image import RgbImage, solid_rgb, write_png_rgb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit and poll a local async VTON job.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/vton_jobs/job.json"))
    parser.add_argument("--work-dir", type=Path, default=Path("artifacts/eval/vton_jobs"))
    parser.add_argument("--request-id", default="req-vton-job-demo")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--poll-timeout-ms", type=int, default=5_000)
    args = parser.parse_args()

    reset_job_queue()
    reset_quota_usage()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    person = args.work_dir / "person.png"
    garment = args.work_dir / "garment.png"
    generated = args.work_dir / "generated.png"
    write_png_rgb(person, _person_image())
    write_png_rgb(garment, _garment_image())

    app = create_app()
    submit = _endpoint_for(app, "/v1/vton/jobs")
    status = _endpoint_for(app, "/v1/vton/jobs/{job_id}")
    metrics = _endpoint_for(app, "/v1/metrics")

    accepted = submit(
        {
            "request_id": args.request_id,
            "person_image_path": str(person),
            "garment_image_path": str(garment),
            "output_image_path": str(generated),
            "timeout_ms": args.timeout_ms,
            "quota_plan": "free",
            "user_id": "demo-user",
        }
    )
    deadline = time.monotonic() + args.poll_timeout_ms / 1000.0
    snapshot = accepted
    while time.monotonic() < deadline:
        snapshot = status(accepted["job_id"])
        if snapshot["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    metrics_response = metrics()
    metrics_body = metrics_response.body.decode("utf-8") if hasattr(metrics_response, "body") else str(metrics_response)
    report = {
        "schema_version": "tryops.vton_async_job_simulation.v1",
        "accepted": accepted,
        "final": snapshot,
        "metrics_contains_queue_depth": "tryops_async_job_queue_depth" in metrics_body,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if snapshot.get("status") == "completed" else 1


def _endpoint_for(app: Any, path: str) -> Any:
    for route in app.routes:
        if route.path == path:
            return route.endpoint
    raise RuntimeError(f"missing route {path}")


def _person_image() -> RgbImage:
    image = bytearray(solid_rgb(96, 128, (235, 238, 242)).pixels)
    width = 96
    for y in range(20, 118):
        for x in range(28, 68):
            index = (y * width + x) * 3
            image[index : index + 3] = bytes([205, 175, 145])
    return RgbImage(width=96, height=128, pixels=bytes(image))


def _garment_image() -> RgbImage:
    image = bytearray(solid_rgb(96, 96, (38, 95, 190)).pixels)
    width = 96
    for y in range(0, 96):
        for x in range(0, 96):
            if x % 18 < 5:
                index = (y * width + x) * 3
                image[index : index + 3] = bytes([245, 245, 255])
    return RgbImage(width=96, height=96, pixels=bytes(image))


if __name__ == "__main__":
    raise SystemExit(main())
