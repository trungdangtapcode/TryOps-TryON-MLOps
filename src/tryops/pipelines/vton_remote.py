from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any


DEFAULT_REAL_VTON_URL = "http://host.docker.internal:18100"
_LOG_LOCK = threading.Lock()


class RealVtonUnavailableError(RuntimeError):
    """Raised when a real VTON adapter is selected but the model service is unavailable."""


def run_remote_fashn_vton(
    *,
    person_image_path: str | Path,
    garment_image_path: str | Path,
    output_image_path: str | Path,
    cache_dir: str | Path,
    timeout_ms: int,
    request_id: str | None = None,
    job_id: str | None = None,
    category: str = "tops",
    garment_photo_type: str = "model",
    num_timesteps: int = 50,
    guidance_scale: float = 1.5,
    seed: int = 555,
    segmentation_free: bool = True,
) -> dict[str, Any]:
    """Run FASHN VTON through the host-side GPU model service.

    Docker GPU runtime is not guaranteed in local demos, so the API calls a host
    service that owns CUDA and model weights. This path intentionally does not
    fall back to the deterministic compositor.
    """

    base_url = os.environ.get("TRYOPS_REAL_VTON_URL", DEFAULT_REAL_VTON_URL).rstrip("/")
    payload = {
        "person_image_path": str(person_image_path),
        "garment_image_path": str(garment_image_path),
        "output_image_path": str(output_image_path),
        "cache_dir": str(cache_dir),
        "category": category,
        "garment_photo_type": garment_photo_type,
        "num_timesteps": num_timesteps,
        "guidance_scale": guidance_scale,
        "seed": seed,
        "segmentation_free": segmentation_free,
    }
    if request_id:
        payload["request_id"] = request_id
    if job_id:
        payload["job_id"] = job_id
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/v1/vton/infer",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    started = perf_counter()
    _emit_real_vton_url_event(
        event_name="tryops.real_vton_url.request_started",
        status="started",
        base_url=base_url,
        request_id=request_id,
        job_id=job_id,
        timeout_ms=timeout_ms,
        attributes={
            "category": category,
            "garment_photo_type": garment_photo_type,
            "num_timesteps": num_timesteps,
            "guidance_scale": guidance_scale,
            "segmentation_free": segmentation_free,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, timeout_ms / 1000.0)) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace") or str(exc)
        _emit_real_vton_url_event(
            event_name="tryops.real_vton_url.request_rejected",
            status="rejected",
            base_url=base_url,
            request_id=request_id,
            job_id=job_id,
            timeout_ms=timeout_ms,
            latency_ms=round((perf_counter() - started) * 1000.0, 3),
            error_code="http_error",
            error_message=message,
            http_status=exc.code,
        )
        raise RealVtonUnavailableError(f"FASHN VTON service rejected request: {message}") from exc
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        _emit_real_vton_url_event(
            event_name="tryops.real_vton_url.request_failed",
            status="failed",
            base_url=base_url,
            request_id=request_id,
            job_id=job_id,
            timeout_ms=timeout_ms,
            latency_ms=round((perf_counter() - started) * 1000.0, 3),
            error_code=type(exc).__name__,
            error_message=str(exc),
        )
        raise RealVtonUnavailableError(
            f"FASHN VTON service unavailable at {base_url}. Start the full app with `make app-up`."
        ) from exc

    if data.get("status") != "completed" or not isinstance(data.get("report"), dict):
        _emit_real_vton_url_event(
            event_name="tryops.real_vton_url.request_rejected",
            status="rejected",
            base_url=base_url,
            request_id=request_id,
            job_id=job_id,
            timeout_ms=timeout_ms,
            latency_ms=round((perf_counter() - started) * 1000.0, 3),
            error_code=str(data.get("error") or "invalid_response"),
            error_message=str(data.get("message") or data.get("error") or "FASHN VTON service failed"),
        )
        raise RealVtonUnavailableError(data.get("message") or data.get("error") or "FASHN VTON service failed")
    _emit_real_vton_url_event(
        event_name="tryops.real_vton_url.request_completed",
        status="completed",
        base_url=base_url,
        request_id=request_id,
        job_id=job_id,
        timeout_ms=timeout_ms,
        latency_ms=round((perf_counter() - started) * 1000.0, 3),
        attributes={"report_status": data.get("status")},
    )
    return data["report"]


def _emit_real_vton_url_event(
    *,
    event_name: str,
    status: str,
    base_url: str,
    request_id: str | None,
    job_id: str | None,
    timeout_ms: int,
    latency_ms: float | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    http_status: int | None = None,
    attributes: dict[str, Any] | None = None,
) -> None:
    path = Path(os.environ.get("TRYOPS_STRUCTURED_LOG_PATH", "artifacts/logs/api_events.jsonl"))
    observed_at = datetime.now(UTC).isoformat()
    severity_text = "ERROR" if status in {"failed", "rejected"} else "INFO"
    record = {
        "schema_version": "tryops.structured_log.v1",
        "timestamp": observed_at,
        "observed_timestamp": observed_at,
        "severity_text": severity_text,
        "severity_number": 17 if severity_text == "ERROR" else 9,
        "event_name": event_name,
        "body": "TRYOPS_REAL_VTON_URL request observed",
        "resource": {
            "service.name": "tryops-api",
            "service.version": "0.1.0",
        },
        "attributes": {
            "workload": "vton",
            "adapter": "fashn-vton-http",
            "tryops_real_vton_url": base_url,
            "http.route": "/v1/vton/infer",
            "http.status_code": http_status,
            "request_id": request_id,
            "job_id": job_id,
            "status": status,
            "timeout_ms": timeout_ms,
            "latency_ms": latency_ms,
            "error_code": error_code,
            "error_message": _sanitize_message(error_message or ""),
            **(attributes or {}),
        },
        "trace_id": None,
        "span_id": None,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK:
            with path.open("a", encoding="utf-8") as output_file:
                output_file.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass


def _sanitize_message(message: str) -> str:
    return message.replace(str(Path.cwd()), "$TRYOPS_ROOT")


run_remote_catvton = run_remote_fashn_vton
