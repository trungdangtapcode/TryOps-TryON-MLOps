#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS_DIR = ROOT / "artifacts" / "models" / "fashn-vton-1.5"
DEFAULT_SERVICE_SCRIPT = ROOT / "scripts" / "serve_fashn_vton.py"


@dataclass(frozen=True)
class WorkerConfig:
    worker_id: str
    gpu_id: str
    gpu_uuid: str
    transport: str
    socket_path: Path | None
    host: str
    port: int | None
    log_file: Path
    pid_file: Path
    structured_log: Path


@dataclass
class WorkerState:
    config: WorkerConfig
    process: subprocess.Popen[bytes] | None = None
    ready: bool = False
    last_probe_status: int | None = None
    last_error: str | None = None
    last_ready_payload: dict[str, Any] = field(default_factory=dict)
    inflight: int = 0
    requests_total: dict[str, int] = field(default_factory=dict)
    latency_ms_count: int = 0
    latency_ms_sum: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None


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
                "service.name": "tryops-fashn-router",
                "service.version": "0.1.0",
            },
            "attributes": attributes or {},
            "trace_id": None,
            "span_id": None,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock:
                with self.path.open("a", encoding="utf-8") as output_file:
                    output_file.write(json.dumps(record, sort_keys=True) + "\n")
        except OSError as exc:
            sys.stderr.write(f"fashn-vton-router: structured log write failed: {exc}\n")


@dataclass(frozen=True)
class RouterConfig:
    host: str
    port: int
    weights_dir: Path
    worker_python: Path
    service_script: Path
    registry_path: Path
    structured_log: Path
    preload: bool
    require_cuda: bool
    allow_cpu_fallback: bool
    workers: list[WorkerConfig]


class FashnVtonRouter:
    def __init__(self, config: RouterConfig, structured_logger: StructuredEventLogger) -> None:
        self.config = config
        self.structured_logger = structured_logger
        self.workers = [WorkerState(worker) for worker in config.workers]
        self.lock = threading.Lock()
        self.scheduler_lock = threading.Lock()
        self.next_worker_index = 0
        self.router_requests_total: dict[str, int] = {}
        self.router_latency_ms_count = 0
        self.router_latency_ms_sum = 0.0

    def start_workers(self) -> None:
        self.config.registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry: list[dict[str, Any]] = []
        for worker in self.workers:
            cfg = worker.config
            cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
            cfg.pid_file.parent.mkdir(parents=True, exist_ok=True)
            cfg.structured_log.parent.mkdir(parents=True, exist_ok=True)
            if cfg.socket_path is not None:
                cfg.socket_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    cfg.socket_path.parent.chmod(0o700)
                except OSError:
                    pass
                try:
                    cfg.socket_path.unlink()
                except FileNotFoundError:
                    pass
            command = [
                str(self.config.worker_python),
                str(self.config.service_script),
                "--weights-dir",
                str(self.config.weights_dir),
                "--device",
                "cuda",
            ]
            if cfg.transport == "unix":
                if cfg.socket_path is None:
                    raise ValueError(f"worker {cfg.worker_id} missing socket_path")
                command.extend(["--unix-socket", str(cfg.socket_path)])
            elif cfg.transport == "tcp":
                if cfg.port is None:
                    raise ValueError(f"worker {cfg.worker_id} missing tcp port")
                command.extend(["--host", cfg.host, "--port", str(cfg.port)])
            else:
                raise ValueError(f"unsupported worker transport: {cfg.transport}")
            if self.config.preload:
                command.append("--preload")

            env = os.environ.copy()
            for inherited_name in (
                "PYTHONHOME",
                "PYTHONPATH",
                "PYTHONSTARTUP",
                "PYTHON_BASIC_REPL",
                "VIRTUAL_ENV",
                "CONDA_PREFIX",
                "CONDA_DEFAULT_ENV",
                "CONDA_PROMPT_MODIFIER",
                "CONDA_SHLVL",
                "CONDA_PYTHON_EXE",
                "CONDA_EXE",
                "_CE_CONDA",
            ):
                env.pop(inherited_name, None)
            env.update(
                {
                    "CUDA_VISIBLE_DEVICES": cfg.gpu_id,
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONUNBUFFERED": "1",
                    "TRYOPS_FASHN_WORKER_ID": cfg.worker_id,
                    "TRYOPS_FASHN_GPU_ID": cfg.gpu_id,
                    "TRYOPS_FASHN_GPU_UUID": cfg.gpu_uuid,
                    "TRYOPS_FASHN_REQUIRE_CUDA": "1" if self.config.require_cuda else "0",
                    "TRYOPS_FASHN_ALLOW_CPU_FALLBACK": "1" if self.config.allow_cpu_fallback else "0",
                    "TRYOPS_FASHN_STRUCTURED_LOG_PATH": str(cfg.structured_log),
                }
            )
            log_handle = cfg.log_file.open("ab")
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    env=env,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
            finally:
                log_handle.close()
            worker.process = process
            cfg.pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
            self.structured_logger.emit(
                event_name="tryops.fashn_router.worker_started",
                body="FASHN router worker process started",
                attributes={
                    "worker_id": cfg.worker_id,
                    "gpu_id": cfg.gpu_id,
                    "gpu_uuid": cfg.gpu_uuid,
                    "transport": cfg.transport,
                    "socket_path": str(cfg.socket_path) if cfg.socket_path else None,
                    "host": cfg.host,
                    "port": cfg.port,
                    "pid": process.pid,
                    "command": command,
                    "log_file": str(cfg.log_file),
                    "structured_log": str(cfg.structured_log),
                },
            )
            registry.append(
                {
                    "worker_id": cfg.worker_id,
                    "pid": process.pid,
                    "gpu_id": cfg.gpu_id,
                    "gpu_uuid": cfg.gpu_uuid,
                    "transport": cfg.transport,
                    "socket_path": str(cfg.socket_path) if cfg.socket_path else None,
                    "host": cfg.host,
                    "port": cfg.port,
                    "log_file": str(cfg.log_file),
                    "structured_log": str(cfg.structured_log),
                }
            )
        self.config.registry_path.write_text(json.dumps({"workers": registry}, indent=2, sort_keys=True), encoding="utf-8")

    def stop_workers(self) -> None:
        for worker in self.workers:
            process = worker.process
            if process is None:
                continue
            if process.poll() is None:
                process.terminate()
        for worker in self.workers:
            process = worker.process
            if process is None:
                continue
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            try:
                worker.config.pid_file.unlink()
            except FileNotFoundError:
                pass
            if worker.config.socket_path is not None:
                try:
                    worker.config.socket_path.unlink()
                except FileNotFoundError:
                    pass

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "model": "fashn-ai/fashn-vton-1.5",
            "router": {
                "host": self.config.host,
                "port": self.config.port,
                "workers": len(self.workers),
                "registry_path": str(self.config.registry_path),
                "preload": self.config.preload,
                "require_cuda": self.config.require_cuda,
                "allow_cpu_fallback": self.config.allow_cpu_fallback,
            },
            "workers": [self._worker_snapshot(worker) for worker in self.workers],
        }

    def readiness(self) -> dict[str, Any]:
        for worker in self.workers:
            self.probe_worker(worker)
        ready_workers = [worker for worker in self.workers if worker.ready and worker.alive()]
        return {
            "status": "ready" if ready_workers else "not_ready",
            "ready": bool(ready_workers),
            "ready_workers": len(ready_workers),
            "workers": [self._worker_snapshot(worker) for worker in self.workers],
        }

    def route_infer(self, body: bytes, timeout_seconds: float) -> tuple[int, dict[str, str], bytes]:
        started = perf_counter()
        request_attrs = _request_attrs_from_body(body)
        worker = self.claim_worker()
        if worker is None:
            payload = {
                "api_version": "v1",
                "status": "rejected",
                "error": "no_ready_fashn_worker",
                "message": "No real FASHN VTON worker is ready. Check the router and worker logs.",
                "workers": [self._worker_snapshot(item) for item in self.workers],
            }
            response = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self._record_router_request(status="rejected", latency_ms=(perf_counter() - started) * 1000.0)
            self.structured_logger.emit(
                event_name="tryops.fashn_router.request_rejected",
                body="FASHN router rejected request because no real worker is ready",
                severity_text="ERROR",
                attributes={
                    "status": "rejected",
                    "error_code": "no_ready_fashn_worker",
                    "tryops_real_vton_url": os.environ.get("TRYOPS_REAL_VTON_URL", ""),
                    **request_attrs,
                    "latency_ms": round((perf_counter() - started) * 1000.0, 3),
                    "ready_workers": 0,
                    "worker_count": len(self.workers),
                },
            )
            return int(HTTPStatus.SERVICE_UNAVAILABLE), {"content-type": "application/json"}, response

        self.structured_logger.emit(
            event_name="tryops.fashn_router.request_started",
            body="FASHN router forwarding request to worker",
            attributes={
                "status": "started",
                "tryops_real_vton_url": os.environ.get("TRYOPS_REAL_VTON_URL", ""),
                **request_attrs,
                "worker_id": worker.config.worker_id,
                "gpu_id": worker.config.gpu_id,
                "gpu_uuid": worker.config.gpu_uuid,
                "transport": worker.config.transport,
            },
        )
        try:
            status, headers, response_body = self._worker_request(
                worker,
                method="POST",
                path="/v1/vton/infer",
                body=body,
                content_type="application/json",
                timeout_seconds=timeout_seconds,
            )
            final_status = "completed" if 200 <= status < 300 else "rejected"
            latency_ms = (perf_counter() - started) * 1000.0
            self._record_worker_request(worker, status=final_status, latency_ms=latency_ms)
            self._record_router_request(status=final_status, latency_ms=latency_ms)
            self.structured_logger.emit(
                event_name=(
                    "tryops.fashn_router.request_completed"
                    if final_status == "completed"
                    else "tryops.fashn_router.request_rejected"
                ),
                body="FASHN router request completed" if final_status == "completed" else "FASHN router request rejected",
                severity_text="INFO" if final_status == "completed" else "ERROR",
                attributes={
                    "status": final_status,
                    "tryops_real_vton_url": os.environ.get("TRYOPS_REAL_VTON_URL", ""),
                    **request_attrs,
                    "worker_id": worker.config.worker_id,
                    "gpu_id": worker.config.gpu_id,
                    "gpu_uuid": worker.config.gpu_uuid,
                    "http.status_code": status,
                    "latency_ms": round(latency_ms, 3),
                },
            )
            return status, headers, response_body
        except Exception as exc:
            latency_ms = (perf_counter() - started) * 1000.0
            with worker.lock:
                worker.ready = False
                worker.last_error = _sanitize_message(str(exc))
            self._record_worker_request(worker, status="failed", latency_ms=latency_ms)
            self._record_router_request(status="failed", latency_ms=latency_ms)
            self.structured_logger.emit(
                event_name="tryops.fashn_router.request_failed",
                body="FASHN router request failed",
                severity_text="ERROR",
                attributes={
                    "status": "failed",
                    "tryops_real_vton_url": os.environ.get("TRYOPS_REAL_VTON_URL", ""),
                    **request_attrs,
                    "worker_id": worker.config.worker_id,
                    "gpu_id": worker.config.gpu_id,
                    "gpu_uuid": worker.config.gpu_uuid,
                    "error_code": type(exc).__name__,
                    "error_message": _sanitize_message(str(exc)),
                    "latency_ms": round(latency_ms, 3),
                },
            )
            payload = {
                "api_version": "v1",
                "status": "rejected",
                "error": type(exc).__name__,
                "message": _sanitize_message(str(exc)),
                "worker_id": worker.config.worker_id,
            }
            response = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            return int(HTTPStatus.BAD_GATEWAY), {"content-type": "application/json"}, response
        finally:
            with worker.lock:
                worker.inflight = max(0, worker.inflight - 1)

    def claim_worker(self) -> WorkerState | None:
        for worker in self.workers:
            if not worker.ready or not worker.alive():
                self.probe_worker(worker)
        with self.scheduler_lock:
            candidates = [worker for worker in self.workers if worker.ready and worker.alive()]
            if not candidates:
                return None
            min_inflight = min(worker.inflight for worker in candidates)
            eligible = {id(worker) for worker in candidates if worker.inflight == min_inflight}
            worker_count = len(self.workers)
            start_index = self.next_worker_index % worker_count
            for offset in range(worker_count):
                index = (start_index + offset) % worker_count
                worker = self.workers[index]
                if id(worker) not in eligible:
                    continue
                self.next_worker_index = (index + 1) % worker_count
                with worker.lock:
                    worker.inflight += 1
                return worker
        return None

    def probe_worker(self, worker: WorkerState) -> None:
        if not worker.alive():
            with worker.lock:
                worker.ready = False
                worker.last_probe_status = None
                worker.last_error = "worker_process_exited"
            return
        try:
            status, _, body = self._worker_request(
                worker,
                method="GET",
                path="/ready",
                body=b"",
                content_type=None,
                timeout_seconds=3.0,
            )
            payload = json.loads(body.decode("utf-8"))
            with worker.lock:
                worker.ready = status == 200 and bool(payload.get("ready"))
                worker.last_probe_status = status
                worker.last_ready_payload = payload if isinstance(payload, dict) else {}
                worker.last_error = None
        except Exception as exc:
            with worker.lock:
                worker.ready = False
                worker.last_probe_status = None
                worker.last_error = _sanitize_message(str(exc))

    def metrics_text(self) -> str:
        readiness = self.readiness()
        labels = {"model": "fashn-ai/fashn-vton-1.5"}
        lines = [
            "# HELP tryops_fashn_router_ready Whether the router has at least one ready real FASHN worker.",
            "# TYPE tryops_fashn_router_ready gauge",
            f"tryops_fashn_router_ready{_prom_labels(labels)} {1 if readiness['ready'] else 0}",
            "# HELP tryops_fashn_router_workers Total configured FASHN workers.",
            "# TYPE tryops_fashn_router_workers gauge",
            f"tryops_fashn_router_workers{_prom_labels(labels)} {len(self.workers)}",
            "# HELP tryops_fashn_router_worker_up Whether the worker process is alive.",
            "# TYPE tryops_fashn_router_worker_up gauge",
        ]
        for worker in self.workers:
            worker_labels = _worker_labels(worker)
            lines.append(f"tryops_fashn_router_worker_up{_prom_labels(worker_labels)} {1 if worker.alive() else 0}")
        lines.extend(
            [
                "# HELP tryops_fashn_router_worker_ready Whether the router sees this worker as ready.",
                "# TYPE tryops_fashn_router_worker_ready gauge",
            ]
        )
        for worker in self.workers:
            worker_labels = _worker_labels(worker)
            lines.append(f"tryops_fashn_router_worker_ready{_prom_labels(worker_labels)} {1 if worker.ready else 0}")
        lines.extend(
            [
                "# HELP tryops_fashn_router_worker_inflight In-flight routed requests by worker.",
                "# TYPE tryops_fashn_router_worker_inflight gauge",
            ]
        )
        for worker in self.workers:
            worker_labels = _worker_labels(worker)
            lines.append(f"tryops_fashn_router_worker_inflight{_prom_labels(worker_labels)} {worker.inflight}")
        with self.lock:
            router_counts = dict(self.router_requests_total)
            router_latency_count = self.router_latency_ms_count
            router_latency_sum = self.router_latency_ms_sum
        lines.extend(
            [
                "# HELP tryops_fashn_router_requests_total Routed inference requests by final status.",
                "# TYPE tryops_fashn_router_requests_total counter",
            ]
        )
        for status, count in sorted(router_counts.items()):
            lines.append(f"tryops_fashn_router_requests_total{_prom_labels(labels | {'status': status})} {count}")
        lines.extend(
            [
                "# HELP tryops_fashn_router_latency_ms Routed inference latency in milliseconds.",
                "# TYPE tryops_fashn_router_latency_ms summary",
                f"tryops_fashn_router_latency_ms_count{_prom_labels(labels)} {router_latency_count}",
                f"tryops_fashn_router_latency_ms_sum{_prom_labels(labels)} {round(router_latency_sum, 3)}",
                "# HELP tryops_fashn_router_worker_requests_total Routed inference requests by worker and final status.",
                "# TYPE tryops_fashn_router_worker_requests_total counter",
            ]
        )
        for worker in self.workers:
            with worker.lock:
                worker_counts = dict(worker.requests_total)
                worker_latency_count = worker.latency_ms_count
                worker_latency_sum = worker.latency_ms_sum
            worker_labels = _worker_labels(worker)
            for status, count in sorted(worker_counts.items()):
                lines.append(
                    f"tryops_fashn_router_worker_requests_total{_prom_labels(worker_labels | {'status': status})} {count}"
                )
            lines.append(f"tryops_fashn_router_worker_latency_ms_count{_prom_labels(worker_labels)} {worker_latency_count}")
            lines.append(f"tryops_fashn_router_worker_latency_ms_sum{_prom_labels(worker_labels)} {round(worker_latency_sum, 3)}")
        lines.append("")
        return "\n".join(lines)

    def _worker_request(
        self,
        worker: WorkerState,
        *,
        method: str,
        path: str,
        body: bytes,
        content_type: str | None,
        timeout_seconds: float,
    ) -> tuple[int, dict[str, str], bytes]:
        cfg = worker.config
        if cfg.transport == "unix":
            if cfg.socket_path is None:
                raise RuntimeError(f"worker {cfg.worker_id} has no socket")
            return _unix_http_request(
                cfg.socket_path,
                method=method,
                path=path,
                body=body,
                content_type=content_type,
                timeout_seconds=timeout_seconds,
            )
        if cfg.port is None:
            raise RuntimeError(f"worker {cfg.worker_id} has no tcp port")
        url = f"http://{cfg.host}:{cfg.port}{path}"
        return _tcp_http_request(url, method=method, body=body, content_type=content_type, timeout_seconds=timeout_seconds)

    def _worker_snapshot(self, worker: WorkerState) -> dict[str, Any]:
        cfg = worker.config
        process = worker.process
        with worker.lock:
            return {
                "worker_id": cfg.worker_id,
                "gpu_id": cfg.gpu_id,
                "gpu_uuid": cfg.gpu_uuid,
                "transport": cfg.transport,
                "socket_path": str(cfg.socket_path) if cfg.socket_path else None,
                "host": cfg.host,
                "port": cfg.port,
                "pid": process.pid if process is not None else None,
                "alive": worker.alive(),
                "exit_code": process.poll() if process is not None else None,
                "ready": worker.ready,
                "last_probe_status": worker.last_probe_status,
                "last_error": worker.last_error,
                "last_ready": worker.last_ready_payload,
                "inflight": worker.inflight,
                "log_file": str(cfg.log_file),
                "structured_log": str(cfg.structured_log),
            }

    def _record_worker_request(self, worker: WorkerState, *, status: str, latency_ms: float) -> None:
        with worker.lock:
            worker.requests_total[status] = worker.requests_total.get(status, 0) + 1
            worker.latency_ms_count += 1
            worker.latency_ms_sum += latency_ms

    def _record_router_request(self, *, status: str, latency_ms: float) -> None:
        with self.lock:
            self.router_requests_total[status] = self.router_requests_total.get(status, 0) + 1
            self.router_latency_ms_count += 1
            self.router_latency_ms_sum += latency_ms


def make_handler(router: FashnVtonRouter) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "TryOpsFashnVtonRouter/1.0"

        def do_GET(self) -> None:
            path = self.path.rstrip("/") or "/"
            if path in {"/", "/health", "/v1/health"}:
                self._json(HTTPStatus.OK, router.health())
                return
            if path in {"/ready", "/v1/ready"}:
                readiness = router.readiness()
                self._json(HTTPStatus.OK if readiness["ready"] else HTTPStatus.SERVICE_UNAVAILABLE, readiness)
                return
            if path in {"/workers", "/v1/workers"}:
                self._json(HTTPStatus.OK, {"workers": router.health()["workers"]})
                return
            if path in {"/metrics", "/v1/metrics"}:
                self._text(HTTPStatus.OK, router.metrics_text(), content_type="text/plain; version=0.0.4")
                return
            self._json(HTTPStatus.NOT_FOUND, {"status": "not_found", "path": self.path})

        def do_POST(self) -> None:
            path = self.path.rstrip("/")
            if path not in {"/v1/vton/infer", "/vton/infer"}:
                self._json(HTTPStatus.NOT_FOUND, {"status": "not_found", "path": self.path})
                return
            length = int(self.headers.get("content-length", "0"))
            if length < 1 or length > 256 * 1024:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "rejected", "error": "invalid_request_body"})
                return
            body = self.rfile.read(length)
            status, headers, response_body = router.route_infer(body, timeout_seconds=900.0)
            self.send_response(status)
            self.send_header("content-type", headers.get("content-type", "application/json"))
            self.send_header("content-length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write("fashn-vton-router: " + (format % args) + "\n")

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


def _request_attrs_from_body(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        "request_id": _optional_str(payload.get("request_id")),
        "job_id": _optional_str(payload.get("job_id")),
        "category": _optional_str(payload.get("category")),
        "garment_photo_type": _optional_str(payload.get("garment_photo_type")),
        "num_timesteps": _optional_int(payload.get("num_timesteps", payload.get("num_inference_steps"))),
    }


def _unix_http_request(
    socket_path: Path,
    *,
    method: str,
    path: str,
    body: bytes,
    content_type: str | None,
    timeout_seconds: float,
) -> tuple[int, dict[str, str], bytes]:
    headers = [
        f"{method} {path} HTTP/1.1",
        "Host: fashn-vton-worker",
        "Connection: close",
        f"Content-Length: {len(body)}",
    ]
    if content_type is not None:
        headers.append(f"Content-Type: {content_type}")
    request_bytes = ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + body
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout_seconds)
        client.connect(str(socket_path))
        client.sendall(request_bytes)
        chunks: list[bytes] = []
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    return _parse_http_response(b"".join(chunks))


def _tcp_http_request(
    url: str,
    *,
    method: str,
    body: bytes,
    content_type: str | None,
    timeout_seconds: float,
) -> tuple[int, dict[str, str], bytes]:
    headers = {}
    if content_type is not None:
        headers["content-type"] = content_type
    req = request.Request(url, data=body if method != "GET" else None, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return response.status, dict(response.headers.items()), response.read()
    except error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def _parse_http_response(raw: bytes) -> tuple[int, dict[str, str], bytes]:
    head, separator, body = raw.partition(b"\r\n\r\n")
    if not separator:
        raise RuntimeError("worker returned a malformed HTTP response")
    lines = head.decode("iso-8859-1").split("\r\n")
    status_parts = lines[0].split()
    if len(status_parts) < 2:
        raise RuntimeError("worker returned a malformed HTTP status line")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        key, _, value = line.partition(":")
        if key:
            headers[key.strip().lower()] = value.strip()
    content_length = headers.get("content-length")
    if content_length is not None:
        body = body[: int(content_length)]
    return int(status_parts[1]), headers, body


def _load_config(args: argparse.Namespace) -> RouterConfig:
    host = _env_value("TRYOPS_FASHN_ROUTER_HOST", args.host)
    port = int(_env_value("TRYOPS_FASHN_ROUTER_PORT", str(args.port)))
    weights_dir = Path(_env_value("FASHN_VTON_WEIGHTS_DIR", str(args.weights_dir))).resolve()
    worker_python = Path(_env_value("FASHN_VTON_PYTHON", str(args.worker_python))).absolute()
    service_script = Path(_env_value("TRYOPS_FASHN_SERVICE_SCRIPT", str(args.service_script))).resolve()
    registry_path = Path(
        _env_value("TRYOPS_FASHN_WORKER_REGISTRY", "artifacts/runtime/fashn-vton-workers.json")
    )
    structured_log = Path(
        _env_value("TRYOPS_FASHN_ROUTER_STRUCTURED_LOG_PATH", "artifacts/logs/fashn_vton_router_events.jsonl")
    )
    transport = _env_value("TRYOPS_FASHN_WORKER_TRANSPORT", args.worker_transport).strip().lower()
    socket_dir = Path(_env_value("TRYOPS_FASHN_WORKER_SOCKET_DIR", str(args.worker_socket_dir)))
    base_port = int(_env_value("TRYOPS_FASHN_WORKER_BASE_PORT", str(args.worker_base_port)))
    preload = _env_bool("TRYOPS_FASHN_WORKER_PRELOAD", default=args.preload)
    require_cuda = _env_bool("TRYOPS_FASHN_REQUIRE_CUDA", default=True)
    allow_cpu_fallback = _env_bool("TRYOPS_FASHN_ALLOW_CPU_FALLBACK", default=False)
    config_file = os.environ.get("TRYOPS_FASHN_WORKERS_CONFIG", str(args.workers_config or "")).strip()
    if config_file:
        workers = _workers_from_file(Path(config_file), default_transport=transport)
    else:
        gpu_ids = _csv(_env_value("TRYOPS_FASHN_GPU_IDS", args.gpu_ids))
        workers = _workers_from_gpu_ids(
            gpu_ids,
            transport=transport,
            socket_dir=socket_dir,
            base_port=base_port,
        )
    return RouterConfig(
        host=host,
        port=port,
        weights_dir=weights_dir,
        worker_python=worker_python,
        service_script=service_script,
        registry_path=registry_path,
        structured_log=structured_log,
        preload=preload,
        require_cuda=require_cuda,
        allow_cpu_fallback=allow_cpu_fallback,
        workers=workers,
    )


def _workers_from_gpu_ids(
    gpu_ids: list[str],
    *,
    transport: str,
    socket_dir: Path,
    base_port: int,
) -> list[WorkerConfig]:
    if not gpu_ids:
        raise ValueError("TRYOPS_FASHN_GPU_IDS must contain at least one GPU id")
    workers = []
    for index, gpu_id in enumerate(gpu_ids):
        worker_id = "fashn-gpu" + _sanitize_id(gpu_id)
        workers.append(
            WorkerConfig(
                worker_id=worker_id,
                gpu_id=gpu_id,
                gpu_uuid="",
                transport=transport,
                socket_path=socket_dir / f"{worker_id}.sock" if transport == "unix" else None,
                host="127.0.0.1",
                port=base_port + index if transport == "tcp" else None,
                log_file=Path("artifacts/logs") / f"fashn-vton-worker-{worker_id}.log",
                pid_file=Path("artifacts/runtime") / f"fashn-vton-worker-{worker_id}.pid",
                structured_log=Path("artifacts/logs") / f"fashn_vton_worker_{worker_id}_events.jsonl",
            )
        )
    return workers


def _workers_from_file(path: Path, *, default_transport: str) -> list[WorkerConfig]:
    data = _load_structured_file(path)
    raw_workers = data.get("workers") if isinstance(data, dict) else None
    if not isinstance(raw_workers, list) or not raw_workers:
        raise ValueError(f"{path} must define a non-empty workers list")
    workers = []
    for index, raw in enumerate(raw_workers):
        if not isinstance(raw, dict):
            raise ValueError(f"worker #{index} in {path} must be an object")
        gpu_id = str(raw.get("gpu_id", raw.get("gpu", index)))
        worker_id = str(raw.get("id", raw.get("worker_id", "fashn-gpu" + _sanitize_id(gpu_id))))
        transport = str(raw.get("transport", default_transport)).strip().lower()
        socket_path = Path(str(raw["socket_path"])) if transport == "unix" and raw.get("socket_path") else None
        if transport == "unix" and socket_path is None:
            socket_path = Path("artifacts/runtime/fashn-workers") / f"{worker_id}.sock"
        port = int(raw["port"]) if raw.get("port") else None
        if transport == "tcp" and port is None:
            port = 43100 + index
        workers.append(
            WorkerConfig(
                worker_id=worker_id,
                gpu_id=gpu_id,
                gpu_uuid=str(raw.get("gpu_uuid", "")),
                transport=transport,
                socket_path=socket_path,
                host=str(raw.get("host", "127.0.0.1")),
                port=port,
                log_file=Path(str(raw.get("log_file", f"artifacts/logs/fashn-vton-worker-{worker_id}.log"))),
                pid_file=Path(str(raw.get("pid_file", f"artifacts/runtime/fashn-vton-worker-{worker_id}.pid"))),
                structured_log=Path(
                    str(raw.get("structured_log", f"artifacts/logs/fashn_vton_worker_{worker_id}_events.jsonl"))
                ),
            )
        )
    return workers


def _load_structured_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError(f"{path} requires PyYAML, or use a .json workers config file") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def _csv(raw: str | None) -> list[str]:
    if not raw:
        return ["0"]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _sanitize_id(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "0"


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


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_value(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw


def _worker_labels(worker: WorkerState) -> dict[str, Any]:
    cfg = worker.config
    return {
        "model": "fashn-ai/fashn-vton-1.5",
        "worker_id": cfg.worker_id,
        "gpu_id": cfg.gpu_id,
        "gpu_uuid": cfg.gpu_uuid,
    }


def _prom_labels(labels: dict[str, Any]) -> str:
    parts = []
    for key, value in sorted(labels.items()):
        if value is None or value == "":
            continue
        parts.append(f'{key}="{_prom_escape(str(value))}"')
    return "{" + ",".join(parts) + "}" if parts else ""


def _prom_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _sanitize_message(message: str) -> str:
    return message.replace(str(ROOT), "$TRYOPS_ROOT")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a stable FASHN VTON router over local HTTP.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18100)
    parser.add_argument("--weights-dir", type=Path, default=DEFAULT_WEIGHTS_DIR)
    parser.add_argument("--worker-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--service-script", type=Path, default=DEFAULT_SERVICE_SCRIPT)
    parser.add_argument("--worker-transport", choices=["unix", "tcp"], default="unix")
    parser.add_argument("--worker-socket-dir", type=Path, default=Path("artifacts/runtime/fashn-workers"))
    parser.add_argument("--worker-base-port", type=int, default=43100)
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--workers-config", type=Path)
    parser.add_argument("--no-preload", action="store_false", dest="preload", default=True)
    args = parser.parse_args()

    config = _load_config(args)
    structured_logger = StructuredEventLogger(config.structured_log)
    router = FashnVtonRouter(config, structured_logger)
    router.start_workers()
    server = ThreadingHTTPServer((config.host, config.port), make_handler(router))
    shutdown_requested = threading.Event()

    def request_shutdown(signum: int, _frame: Any) -> None:
        if shutdown_requested.is_set():
            return
        shutdown_requested.set()
        print(f"FASHN VTON router received signal {signum}; stopping", flush=True)
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    print(f"FASHN VTON router listening on http://{config.host}:{config.port}", flush=True)
    print(f"workers: {len(config.workers)} registry={config.registry_path}", flush=True)
    structured_logger.emit(
        event_name="tryops.fashn_router.service_started",
        body="FASHN router started",
        attributes={
            "host": config.host,
            "port": config.port,
            "tryops_real_vton_url": os.environ.get("TRYOPS_REAL_VTON_URL", ""),
            "weights_dir": str(config.weights_dir),
            "worker_count": len(config.workers),
            "registry_path": str(config.registry_path),
            "preload": config.preload,
            "require_cuda": config.require_cuda,
            "allow_cpu_fallback": config.allow_cpu_fallback,
        },
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        router.stop_workers()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
