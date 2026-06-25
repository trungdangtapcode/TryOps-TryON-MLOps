#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_fashn_vton_single import DEFAULT_WEIGHTS_DIR, FashnVtonRunner  # noqa: E402


class ResourceNotReadyError(RuntimeError):
    pass


class StructuredEventLogger:
    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path) if path else None
        self.lock = threading.Lock()

    def emit(
        self,
        *,
        event_name: str,
        body: str,
        attributes: dict[str, Any] | None = None,
        severity_text: str = "INFO",
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        if self.path is None:
            return
        observed_at = datetime.now(UTC).isoformat()
        record = {
            "schema_version": "tryops.structured_log.v1",
            "timestamp": observed_at,
            "observed_timestamp": observed_at,
            "severity_text": severity_text,
            "severity_number": 17 if severity_text == "ERROR" else 9,
            "event_name": event_name,
            "body": body,
            "resource": {
                "service.name": "tryops-fashn-vton",
                "service.version": "0.1.0",
            },
            "attributes": attributes or {},
            "trace_id": trace_id,
            "span_id": span_id,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock:
                with self.path.open("a", encoding="utf-8") as output_file:
                    output_file.write(json.dumps(record, sort_keys=True) + "\n")
        except OSError as exc:
            sys.stderr.write(f"fashn-vton-service: structured log write failed: {exc}\n")


class FashnVtonService:
    def __init__(self, *, weights_dir: Path, device: str | None) -> None:
        self.runner = FashnVtonRunner(weights_dir=weights_dir, device=device)
        self.lock = threading.Lock()
        self.min_available_mb = int(os.environ.get("TRYOPS_FASHN_MIN_AVAILABLE_MB", "4096"))

    def health(self) -> dict[str, Any]:
        available_mb = _mem_available_mb()
        return {
            "status": "ok",
            "model": "fashn-ai/fashn-vton-1.5",
            "weights_dir": str(self.runner.weights_dir),
            "loaded": self.runner._pipeline is not None,
            "gpu_first_load": os.environ.get("FASHN_VTON_GPU_FIRST_LOAD", "1"),
            "memory": {
                "available_mb": available_mb,
                "min_available_mb": self.min_available_mb,
                "safe_to_load": self.runner._pipeline is not None
                or self.min_available_mb <= 0
                or available_mb >= self.min_available_mb,
            },
        }

    def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_memory_budget()
        with self.lock:
            report = self.runner.run(
                person_image_path=_required_str(payload, "person_image_path"),
                garment_image_path=_required_str(payload, "garment_image_path"),
                output_image_path=_required_str(payload, "output_image_path"),
                category=str(payload.get("category", "tops")),
                garment_photo_type=str(payload.get("garment_photo_type", "model")),
                num_timesteps=int(payload.get("num_timesteps", payload.get("num_inference_steps", 50))),
                guidance_scale=float(payload.get("guidance_scale", 1.5)),
                seed=int(payload.get("seed", 555)),
                segmentation_free=bool(payload.get("segmentation_free", True)),
            )
        return {
            "api_version": "v1",
            "status": "completed",
            "model": "fashn-ai/fashn-vton-1.5",
            "report": report,
        }

    def _ensure_memory_budget(self) -> None:
        if self.runner._pipeline is not None:
            return
        available_mb = _mem_available_mb()
        if self.min_available_mb > 0 and available_mb < self.min_available_mb:
            raise ResourceNotReadyError(
                f"Refusing to load FASHN VTON: only {available_mb}MiB RAM available, "
                f"need at least {self.min_available_mb}MiB. Close other apps or stop services before generating."
            )


def make_handler(service: FashnVtonService, structured_logger: StructuredEventLogger) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "TryOpsFashnVton/1.0"

        def do_GET(self) -> None:
            if self.path.rstrip("/") in {"", "/health", "/v1/health"}:
                self._json(HTTPStatus.OK, service.health())
                return
            self._json(HTTPStatus.NOT_FOUND, {"status": "not_found", "path": self.path})

        def do_POST(self) -> None:
            if self.path.rstrip("/") not in {"/v1/vton/infer", "/vton/infer"}:
                self._json(HTTPStatus.NOT_FOUND, {"status": "not_found", "path": self.path})
                return
            started = perf_counter()
            attributes: dict[str, Any] = {
                "http.method": "POST",
                "http.route": "/v1/vton/infer",
                "status": "started",
                "model": "fashn-ai/fashn-vton-1.5",
            }
            trace_id: str | None = None
            span_id: str | None = None
            try:
                payload = self._read_json()
                attributes.update(_request_attributes(payload, service))
                trace_id, span_id = _trace_ids_from_payload(payload)
                structured_logger.emit(
                    event_name="tryops.fashn_vton.request_started",
                    body="FASHN VTON inference started",
                    attributes=attributes.copy(),
                    trace_id=trace_id,
                    span_id=span_id,
                )
                response = service.infer(payload)
                completed_attributes = attributes.copy()
                completed_attributes.update(
                    {
                        "status": "completed",
                        "latency_ms": round((perf_counter() - started) * 1000.0, 3),
                        "model_loaded": service.runner._pipeline is not None,
                        "metrics": _safe_report_metrics(response.get("report")),
                    }
                )
                structured_logger.emit(
                    event_name="tryops.fashn_vton.request_completed",
                    body="FASHN VTON inference completed",
                    attributes=completed_attributes,
                    trace_id=trace_id,
                    span_id=span_id,
                )
                self._json(HTTPStatus.OK, response)
            except ResourceNotReadyError as exc:
                failed_attributes = attributes.copy()
                failed_attributes.update(
                    {
                        "status": "rejected",
                        "latency_ms": round((perf_counter() - started) * 1000.0, 3),
                        "error_type": type(exc).__name__,
                        "error_code": "insufficient_host_memory",
                        "error_message": _sanitize_message(str(exc)),
                        "model_loaded": service.runner._pipeline is not None,
                    }
                )
                structured_logger.emit(
                    event_name="tryops.fashn_vton.request_rejected",
                    severity_text="ERROR",
                    body="FASHN VTON inference rejected",
                    attributes=failed_attributes,
                    trace_id=trace_id,
                    span_id=span_id,
                )
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "api_version": "v1",
                        "status": "rejected",
                        "error": "insufficient_host_memory",
                        "message": str(exc),
                    },
                )
            except Exception as exc:
                failed_attributes = attributes.copy()
                failed_attributes.update(
                    {
                        "status": "failed",
                        "latency_ms": round((perf_counter() - started) * 1000.0, 3),
                        "error_type": type(exc).__name__,
                        "error_code": type(exc).__name__,
                        "error_message": _sanitize_message(str(exc)),
                        "model_loaded": service.runner._pipeline is not None,
                    }
                )
                structured_logger.emit(
                    event_name="tryops.fashn_vton.request_failed",
                    severity_text="ERROR",
                    body="FASHN VTON inference failed",
                    attributes=failed_attributes,
                    trace_id=trace_id,
                    span_id=span_id,
                )
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "api_version": "v1",
                        "status": "rejected",
                        "error": type(exc).__name__,
                        "message": str(exc),
                    },
                )

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write("fashn-vton-service: " + (format % args) + "\n")

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            if length < 1 or length > 128 * 1024:
                raise ValueError("request JSON body is missing or too large")
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("request body must be a JSON object")
            return data

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(int(status))
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _required_str(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value


def _request_attributes(payload: dict[str, Any], service: FashnVtonService) -> dict[str, Any]:
    return {
        "request_id": _optional_str(payload.get("request_id")),
        "job_id": _optional_str(payload.get("job_id")),
        "category": _optional_str(payload.get("category")) or "tops",
        "garment_photo_type": _optional_str(payload.get("garment_photo_type")) or "model",
        "num_timesteps": _optional_int(payload.get("num_timesteps", payload.get("num_inference_steps", 50))),
        "guidance_scale": _optional_float(payload.get("guidance_scale", 1.5)),
        "seed": _optional_int(payload.get("seed", 555)),
        "segmentation_free": bool(payload.get("segmentation_free", True)),
        "has_person_image_path": bool(_optional_str(payload.get("person_image_path"))),
        "has_garment_image_path": bool(_optional_str(payload.get("garment_image_path"))),
        "has_output_image_path": bool(_optional_str(payload.get("output_image_path"))),
        "weights_dir": str(service.runner.weights_dir),
        "model_loaded": service.runner._pipeline is not None,
        "available_memory_mb": _mem_available_mb(),
        "min_available_memory_mb": service.min_available_mb,
    }


def _trace_ids_from_payload(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    traceparent = _optional_str(payload.get("traceparent"))
    if not traceparent:
        return None, None
    parts = traceparent.split("-")
    if len(parts) >= 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
        return parts[1], parts[2]
    return None, None


def _safe_report_metrics(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, (int, float, bool)) or value is None:
            safe[str(key)] = value
    return safe


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sanitize_message(message: str) -> str:
    return message.replace(str(ROOT), "$TRYOPS_ROOT")


def _mem_available_mb() -> int:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return 0
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve FASHN VTON v1.5 over local HTTP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18101)
    parser.add_argument("--weights-dir", type=Path, default=DEFAULT_WEIGHTS_DIR)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--preload", action="store_true", help="Load model before accepting requests.")
    args = parser.parse_args()

    structured_logger = StructuredEventLogger(
        os.environ.get("TRYOPS_FASHN_STRUCTURED_LOG_PATH", "artifacts/logs/fashn_vton_events.jsonl")
    )
    service = FashnVtonService(weights_dir=args.weights_dir, device=args.device)
    if args.preload:
        service.runner.load()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(service, structured_logger))
    print(f"FASHN VTON service listening on http://{args.host}:{args.port}", flush=True)
    print(f"weights: {args.weights_dir}", flush=True)
    structured_logger.emit(
        event_name="tryops.fashn_vton.service_started",
        body="FASHN VTON service started",
        attributes={
            "host": args.host,
            "port": args.port,
            "weights_dir": str(args.weights_dir),
            "device": args.device,
            "preload": bool(args.preload),
            "gpu_first_load": os.environ.get("FASHN_VTON_GPU_FIRST_LOAD", "1"),
            "min_available_memory_mb": service.min_available_mb,
        },
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nFASHN VTON service stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
