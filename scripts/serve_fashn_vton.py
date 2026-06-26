#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socketserver
import sys
import threading
import importlib.util
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
        self.worker_id = os.environ.get("TRYOPS_FASHN_WORKER_ID", "fashn-single")
        self.gpu_id = os.environ.get("TRYOPS_FASHN_GPU_ID", "")
        self.gpu_uuid = os.environ.get("TRYOPS_FASHN_GPU_UUID", "")
        self.require_cuda = _env_bool("TRYOPS_FASHN_REQUIRE_CUDA", default=device == "cuda")
        self.allow_cpu_fallback = _env_bool("TRYOPS_FASHN_ALLOW_CPU_FALLBACK", default=False)
        self.metrics_lock = threading.Lock()
        self.inflight = 0
        self.requests_total: dict[str, int] = {}
        self.errors_total: dict[str, int] = {}
        self.latency_ms_count = 0
        self.latency_ms_sum = 0.0

    def health(self) -> dict[str, Any]:
        available_mb = _mem_available_mb()
        cuda = _cuda_state()
        return {
            "status": "ok",
            "worker_id": self.worker_id,
            "gpu_id": self.gpu_id,
            "gpu_uuid": self.gpu_uuid,
            "model": "fashn-ai/fashn-vton-1.5",
            "weights_dir": str(self.runner.weights_dir),
            "device": self.runner.device,
            "loaded": self.runner._pipeline is not None,
            "ready": self.ready()["ready"],
            "cuda": cuda,
            "require_cuda": self.require_cuda,
            "allow_cpu_fallback": self.allow_cpu_fallback,
            "gpu_first_load": os.environ.get("FASHN_VTON_GPU_FIRST_LOAD", "1"),
            "memory": {
                "available_mb": available_mb,
                "min_available_mb": self.min_available_mb,
                "safe_to_load": self.runner._pipeline is not None
                or self.min_available_mb <= 0
                or available_mb >= self.min_available_mb,
            },
        }

    def ready(self) -> dict[str, Any]:
        loaded = self.runner._pipeline is not None
        available_mb = _mem_available_mb()
        memory_safe = loaded or self.min_available_mb <= 0 or available_mb >= self.min_available_mb
        cuda = _cuda_state()
        cuda_ok = (not self.require_cuda) or bool(cuda["available"])
        ready = loaded and memory_safe and cuda_ok
        reasons: list[str] = []
        if not loaded:
            reasons.append("model_not_loaded")
        if not memory_safe:
            reasons.append("insufficient_host_memory")
        if not cuda_ok:
            reasons.append("cuda_unavailable")
        return {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "worker_id": self.worker_id,
            "gpu_id": self.gpu_id,
            "gpu_uuid": self.gpu_uuid,
            "model": "fashn-ai/fashn-vton-1.5",
            "loaded": loaded,
            "device": self.runner.device,
            "require_cuda": self.require_cuda,
            "allow_cpu_fallback": self.allow_cpu_fallback,
            "cuda": cuda,
            "memory": {
                "available_mb": available_mb,
                "min_available_mb": self.min_available_mb,
                "safe_to_load": memory_safe,
            },
            "reasons": reasons,
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

    def begin_request(self) -> None:
        with self.metrics_lock:
            self.inflight += 1

    def finish_request(self, *, status: str, latency_ms: float, error_code: str | None = None) -> None:
        with self.metrics_lock:
            self.inflight = max(0, self.inflight - 1)
            self.requests_total[status] = self.requests_total.get(status, 0) + 1
            if error_code:
                self.errors_total[error_code] = self.errors_total.get(error_code, 0) + 1
            self.latency_ms_count += 1
            self.latency_ms_sum += latency_ms

    def metrics_text(self) -> str:
        ready = self.ready()
        labels = {
            "worker_id": self.worker_id,
            "gpu_id": self.gpu_id,
            "gpu_uuid": self.gpu_uuid,
            "model": "fashn-ai/fashn-vton-1.5",
        }
        lines = [
            "# HELP tryops_fashn_worker_ready Whether the FASHN worker has a real loaded model and is ready.",
            "# TYPE tryops_fashn_worker_ready gauge",
            f"tryops_fashn_worker_ready{_prom_labels(labels)} {1 if ready['ready'] else 0}",
            "# HELP tryops_fashn_worker_inflight In-flight inference requests on the worker.",
            "# TYPE tryops_fashn_worker_inflight gauge",
            f"tryops_fashn_worker_inflight{_prom_labels(labels)} {self.inflight}",
            "# HELP tryops_fashn_worker_model_loaded Whether the FASHN model is loaded in this worker.",
            "# TYPE tryops_fashn_worker_model_loaded gauge",
            f"tryops_fashn_worker_model_loaded{_prom_labels(labels)} {1 if self.runner._pipeline is not None else 0}",
            "# HELP tryops_fashn_worker_cuda_available Whether PyTorch reports CUDA as available.",
            "# TYPE tryops_fashn_worker_cuda_available gauge",
            f"tryops_fashn_worker_cuda_available{_prom_labels(labels)} {1 if ready['cuda']['available'] else 0}",
            "# HELP tryops_fashn_worker_host_memory_available_mb Host MemAvailable for this process.",
            "# TYPE tryops_fashn_worker_host_memory_available_mb gauge",
            f"tryops_fashn_worker_host_memory_available_mb{_prom_labels(labels)} {ready['memory']['available_mb']}",
            "# HELP tryops_fashn_worker_requests_total Worker inference requests by final status.",
            "# TYPE tryops_fashn_worker_requests_total counter",
        ]
        with self.metrics_lock:
            request_counts = dict(self.requests_total)
            error_counts = dict(self.errors_total)
            latency_count = self.latency_ms_count
            latency_sum = self.latency_ms_sum
        for status, count in sorted(request_counts.items()):
            metric_labels = labels | {"status": status}
            lines.append(f"tryops_fashn_worker_requests_total{_prom_labels(metric_labels)} {count}")
        lines.extend(
            [
                "# HELP tryops_fashn_worker_errors_total Worker inference errors by error code.",
                "# TYPE tryops_fashn_worker_errors_total counter",
            ]
        )
        for error_code, count in sorted(error_counts.items()):
            metric_labels = labels | {"error_code": error_code}
            lines.append(f"tryops_fashn_worker_errors_total{_prom_labels(metric_labels)} {count}")
        lines.extend(
            [
                "# HELP tryops_fashn_worker_latency_ms Request latency in milliseconds.",
                "# TYPE tryops_fashn_worker_latency_ms summary",
                f"tryops_fashn_worker_latency_ms_count{_prom_labels(labels)} {latency_count}",
                f"tryops_fashn_worker_latency_ms_sum{_prom_labels(labels)} {round(latency_sum, 3)}",
            ]
        )
        return "\n".join(lines) + "\n"


def make_handler(service: FashnVtonService, structured_logger: StructuredEventLogger) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "TryOpsFashnVton/1.0"

        def do_GET(self) -> None:
            if self.path.rstrip("/") in {"", "/health", "/v1/health"}:
                self._json(HTTPStatus.OK, service.health())
                return
            if self.path.rstrip("/") in {"/ready", "/v1/ready"}:
                readiness = service.ready()
                self._json(HTTPStatus.OK if readiness["ready"] else HTTPStatus.SERVICE_UNAVAILABLE, readiness)
                return
            if self.path.rstrip("/") in {"/metrics", "/v1/metrics"}:
                self._text(HTTPStatus.OK, service.metrics_text(), content_type="text/plain; version=0.0.4")
                return
            self._json(HTTPStatus.NOT_FOUND, {"status": "not_found", "path": self.path})

        def do_POST(self) -> None:
            if self.path.rstrip("/") not in {"/v1/vton/infer", "/vton/infer"}:
                self._json(HTTPStatus.NOT_FOUND, {"status": "not_found", "path": self.path})
                return
            started = perf_counter()
            service.begin_request()
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
                latency_ms = round((perf_counter() - started) * 1000.0, 3)
                completed_attributes.update(
                    {
                        "status": "completed",
                        "latency_ms": latency_ms,
                        "model_loaded": service.runner._pipeline is not None,
                        "metrics": _safe_report_metrics(response.get("report")),
                    }
                )
                service.finish_request(status="completed", latency_ms=latency_ms)
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
                latency_ms = round((perf_counter() - started) * 1000.0, 3)
                service.finish_request(
                    status="rejected",
                    latency_ms=latency_ms,
                    error_code="insufficient_host_memory",
                )
                failed_attributes.update(
                    {
                        "status": "rejected",
                        "latency_ms": latency_ms,
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
                latency_ms = round((perf_counter() - started) * 1000.0, 3)
                service.finish_request(
                    status="failed",
                    latency_ms=latency_ms,
                    error_code=type(exc).__name__,
                )
                failed_attributes.update(
                    {
                        "status": "failed",
                        "latency_ms": latency_ms,
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

        def _text(self, status: HTTPStatus, body_text: str, *, content_type: str) -> None:
            body = body_text.encode("utf-8")
            self.send_response(int(status))
            self.send_header("content-type", content_type)
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


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _cuda_state() -> dict[str, Any]:
    try:
        import torch
    except ImportError:
        return {
            "available": False,
            "device_count": 0,
            "current_device": None,
            "device_name": None,
            "error": "torch_not_installed",
        }
    try:
        available = bool(torch.cuda.is_available())
        current_device = int(torch.cuda.current_device()) if available else None
        device_name = torch.cuda.get_device_name(current_device) if current_device is not None else None
        return {
            "available": available,
            "device_count": int(torch.cuda.device_count()) if available else 0,
            "current_device": current_device,
            "device_name": device_name,
            "error": None,
        }
    except Exception as exc:
        return {
            "available": False,
            "device_count": 0,
            "current_device": None,
            "device_name": None,
            "error": _sanitize_message(str(exc)),
        }


def _mem_available_mb() -> int:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return 0
    return 0


def _prom_labels(labels: dict[str, Any]) -> str:
    parts = []
    for key, value in sorted(labels.items()):
        if value is None or value == "":
            continue
        parts.append(f'{key}="{_prom_escape(str(value))}"')
    return "{" + ",".join(parts) + "}" if parts else ""


def _prom_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class ThreadingUnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve FASHN VTON v1.5 over local HTTP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18101)
    parser.add_argument("--unix-socket", type=Path, help="Serve HTTP over this Unix socket instead of TCP.")
    parser.add_argument("--weights-dir", type=Path, default=DEFAULT_WEIGHTS_DIR)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--preload", action="store_true", help="Load model before accepting requests.")
    args = parser.parse_args()

    structured_logger = StructuredEventLogger(
        os.environ.get("TRYOPS_FASHN_STRUCTURED_LOG_PATH", "artifacts/logs/fashn_vton_events.jsonl")
    )
    service = FashnVtonService(weights_dir=args.weights_dir, device=args.device)
    if args.preload:
        try:
            service.runner.load()
        except Exception:
            sys.stderr.write(
                "fashn-vton-service: preload failed with "
                f"executable={sys.executable} cv2_spec={importlib.util.find_spec('cv2')} "
                f"sys_path={sys.path}\n"
            )
            raise

    if args.unix_socket:
        args.unix_socket.parent.mkdir(parents=True, exist_ok=True)
        try:
            args.unix_socket.unlink()
        except FileNotFoundError:
            pass
        server = ThreadingUnixHTTPServer(str(args.unix_socket), make_handler(service, structured_logger))
        endpoint = f"unix://{args.unix_socket}"
    else:
        server = ThreadingHTTPServer((args.host, args.port), make_handler(service, structured_logger))
        endpoint = f"http://{args.host}:{args.port}"
    print(f"FASHN VTON service listening on {endpoint}", flush=True)
    print(f"weights: {args.weights_dir}", flush=True)
    structured_logger.emit(
        event_name="tryops.fashn_vton.service_started",
        body="FASHN VTON service started",
        attributes={
            "host": args.host,
            "port": args.port,
            "endpoint": endpoint,
            "unix_socket": str(args.unix_socket) if args.unix_socket else None,
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
    finally:
        server.server_close()
        if args.unix_socket:
            try:
                args.unix_socket.unlink()
            except FileNotFoundError:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
