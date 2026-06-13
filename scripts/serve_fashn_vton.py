#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_fashn_vton_single import DEFAULT_WEIGHTS_DIR, FashnVtonRunner  # noqa: E402


class ResourceNotReadyError(RuntimeError):
    pass


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


def make_handler(service: FashnVtonService) -> type[BaseHTTPRequestHandler]:
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
            try:
                payload = self._read_json()
                self._json(HTTPStatus.OK, service.infer(payload))
            except ResourceNotReadyError as exc:
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

    service = FashnVtonService(weights_dir=args.weights_dir, device=args.device)
    if args.preload:
        service.runner.load()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    print(f"FASHN VTON service listening on http://{args.host}:{args.port}", flush=True)
    print(f"weights: {args.weights_dir}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nFASHN VTON service stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
