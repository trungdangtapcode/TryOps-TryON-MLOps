from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import request

from tryops.api import create_app
from tryops.jobs import reset_job_queue
from tryops.observability import reset_metrics
from tryops.quota import reset_quota_usage
from tryops.simple_image import RgbImage, solid_rgb, write_png_rgb


def run_endpoint_smoke(
    *,
    output_dir: str | Path,
    base_url: str | None = None,
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    image_dir = root / "inputs"
    image_dir.mkdir(parents=True, exist_ok=True)
    person_path = image_dir / "person.png"
    garment_path = image_dir / "garment.png"
    vton_output_path = root / "vton_output.png"
    write_png_rgb(person_path, _person_image())
    write_png_rgb(garment_path, _garment_image())

    reset_metrics()
    reset_quota_usage()
    reset_job_queue()

    client = _HttpClient(base_url) if base_url else _RouteClient()
    checks = [
        _check_ready(client),
        _check_llm_generate(client),
        _check_vton_infer(client, person_path=person_path, garment_path=garment_path, output_path=vton_output_path),
        _check_metrics(client),
    ]
    report = {
        "schema_version": "tryops.endpoint_smoke.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "http" if base_url else "in_process_route_client",
        "base_url": base_url,
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
        "artifacts": {
            "person_image": str(person_path),
            "garment_image": str(garment_path),
            "vton_output": str(vton_output_path),
        },
    }
    (root / "deployed_endpoint_smoke.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


class _RouteClient:
    def __init__(self) -> None:
        self._app = create_app()

    def get(self, path: str) -> tuple[int, Any]:
        endpoint = self._endpoint_for(path)
        response = endpoint()
        return 200, _normalize_route_response(response)

    def post(self, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
        endpoint = self._endpoint_for(path)
        response = endpoint(payload)
        return 200, _normalize_route_response(response)

    def _endpoint_for(self, path: str) -> Any:
        for route in self._app.routes:
            if getattr(route, "path", None) == path:
                return route.endpoint
        raise KeyError(f"route not found: {path}")


class _HttpClient:
    def __init__(self, base_url: str | None) -> None:
        if not base_url:
            raise ValueError("base_url is required for HTTP smoke mode")
        self._base_url = base_url.rstrip("/")

    def get(self, path: str) -> tuple[int, Any]:
        with request.urlopen(f"{self._base_url}{path}", timeout=30) as response:
            body = response.read().decode("utf-8")
            return int(response.status), _decode_response(body, response.headers.get("content-type", ""))

    def post(self, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self._base_url}{path}",
            data=body,
            method="POST",
            headers={"content-type": "application/json"},
        )
        with request.urlopen(http_request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
            return int(response.status), _decode_response(response_body, response.headers.get("content-type", ""))


def _check_ready(client: Any) -> dict[str, Any]:
    started = time.perf_counter()
    status_code, payload = client.get("/v1/ready")
    passed = status_code == 200 and isinstance(payload, dict) and payload.get("status") == "ready"
    return {
        "name": "ready",
        "endpoint": "GET /v1/ready",
        "status_code": status_code,
        "latency_ms": _elapsed_ms(started),
        "passed": passed,
        "status": payload.get("status") if isinstance(payload, dict) else "invalid_response",
        "component_count": len(payload.get("components", {})) if isinstance(payload, dict) else 0,
    }


def _check_llm_generate(client: Any) -> dict[str, Any]:
    started = time.perf_counter()
    status_code, payload = client.post(
        "/v1/llm/generate",
        {
            "request_id": "req-endpoint-smoke-llm",
            "prompt": "Explain TryOps monitoring, registry, and rollback in three concise points.",
            "model_alias": "baseline",
            "max_tokens": 96,
            "structured": True,
            "quota_plan": "free",
            "user_id": "endpoint-smoke-user",
        },
    )
    metrics = payload.get("metrics", {}) if isinstance(payload, dict) else {}
    passed = (
        status_code == 200
        and isinstance(payload, dict)
        and payload.get("status") == "completed"
        and float(metrics.get("tokens_per_second", 0.0)) > 0.0
    )
    return {
        "name": "llm_generate",
        "endpoint": "POST /v1/llm/generate",
        "status_code": status_code,
        "latency_ms": _elapsed_ms(started),
        "passed": passed,
        "response_status": payload.get("status") if isinstance(payload, dict) else "invalid_response",
        "model_alias": payload.get("model_alias") if isinstance(payload, dict) else None,
        "tokens_per_second": metrics.get("tokens_per_second"),
        "quality_score": payload.get("quality_score") if isinstance(payload, dict) else None,
        "quota_allowed": payload.get("quota", {}).get("allowed") if isinstance(payload, dict) else None,
    }


def _check_vton_infer(
    client: Any,
    *,
    person_path: Path,
    garment_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    status_code, payload = client.post(
        "/v1/vton/infer",
        {
            "request_id": "req-endpoint-smoke-vton",
            "person_image_path": str(person_path),
            "garment_image_path": str(garment_path),
            "output_image_path": str(output_path),
            "model_alias": "champion",
            "timeout_ms": 30000,
            "quota_plan": "free",
            "user_id": "endpoint-smoke-user",
        },
    )
    report = payload.get("report", {}) if isinstance(payload, dict) else {}
    output = report.get("output", {}) if isinstance(report, dict) else {}
    passed = (
        status_code == 200
        and isinstance(payload, dict)
        and payload.get("status") == "completed"
        and output_path.exists()
        and output.get("checksum")
    )
    return {
        "name": "vton_infer",
        "endpoint": "POST /v1/vton/infer",
        "status_code": status_code,
        "latency_ms": _elapsed_ms(started),
        "passed": bool(passed),
        "response_status": payload.get("status") if isinstance(payload, dict) else "invalid_response",
        "model_alias": payload.get("model_alias") if isinstance(payload, dict) else None,
        "output_exists": output_path.exists(),
        "output_checksum": output.get("checksum"),
        "quota_allowed": payload.get("quota", {}).get("allowed") if isinstance(payload, dict) else None,
    }


def _check_metrics(client: Any) -> dict[str, Any]:
    started = time.perf_counter()
    status_code, payload = client.get("/v1/metrics")
    body = str(payload)
    required_metrics = [
        "tryops_api_requests_total",
        "tryops_api_latency_ms_count",
        "tryops_process_memory_gb",
        "tryops_async_job_queue_depth",
    ]
    missing = [metric for metric in required_metrics if metric not in body]
    return {
        "name": "metrics",
        "endpoint": "GET /v1/metrics",
        "status_code": status_code,
        "latency_ms": _elapsed_ms(started),
        "passed": status_code == 200 and not missing,
        "missing_metrics": missing,
        "contains_llm_counter": 'workload="llm"' in body,
        "contains_vton_counter": 'workload="vton"' in body,
    }


def _decode_response(body: str, content_type: str) -> Any:
    if "application/json" in content_type:
        return json.loads(body)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def _normalize_route_response(response: Any) -> Any:
    if hasattr(response, "body"):
        body = response.body.decode("utf-8")
        media_type = getattr(response, "media_type", "") or ""
        return _decode_response(body, media_type)
    return response


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


def _person_image() -> RgbImage:
    image = bytearray(solid_rgb(128, 160, (236, 238, 242)).pixels)
    width = 128
    for y in range(24, 148):
        for x in range(38, 91):
            index = (y * width + x) * 3
            image[index : index + 3] = bytes([212, 178, 146])
    for y in range(56, 148):
        for x in range(28, 100):
            if 36 <= x <= 94:
                index = (y * width + x) * 3
                image[index : index + 3] = bytes([180, 190, 205])
    return RgbImage(width=128, height=160, pixels=bytes(image))


def _garment_image() -> RgbImage:
    image = bytearray(solid_rgb(80, 80, (38, 82, 188)).pixels)
    width = 80
    for y in range(80):
        for x in range(80):
            if x % 13 < 3 or y % 17 < 3:
                index = (y * width + x) * 3
                image[index : index + 3] = bytes([245, 245, 255])
    return RgbImage(width=80, height=80, pixels=bytes(image))
