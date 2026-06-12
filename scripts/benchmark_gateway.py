#!/usr/bin/env python3
"""Native-vs-Python serving benchmark orchestrator.

Starts the compiled Rust gateway and the Python FastAPI app, warms them, drives
identical load at ``/health``, and writes a ``tryops.gateway_benchmark.v1``
artifact with the throughput/latency comparison and the native speedup factor.
Self-contained: manages both server subprocesses and tears them down.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.gateway_benchmark import run_load  # noqa: E402


def _wait_ready(url: str, timeout_s: float = 15.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Native Rust gateway vs Python FastAPI load benchmark.")
    parser.add_argument("--requests", type=int, default=3000)
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--gateway-bin", default="artifacts/native/tryops-gateway")
    parser.add_argument("--gateway-port", type=int, default=18091)
    parser.add_argument("--python-port", type=int, default=18092)
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/gateway_benchmark/gateway_benchmark.json"))
    args = parser.parse_args()

    results: dict[str, dict] = {}
    procs: list[subprocess.Popen] = []
    try:
        # --- Native Rust gateway ---
        gw_bin = Path(args.gateway_bin)
        if gw_bin.exists():
            env = os.environ.copy()
            env["TRYOPS_GATEWAY_ADDR"] = f"127.0.0.1:{args.gateway_port}"
            gw = subprocess.Popen([str(gw_bin)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            procs.append(gw)
            gw_url = f"http://127.0.0.1:{args.gateway_port}/health"
            if _wait_ready(gw_url):
                run_load(gw_url, total_requests=200, concurrency=8)  # warmup
                results["native_rust_gateway"] = run_load(
                    gw_url, total_requests=args.requests, concurrency=args.concurrency
                )
            else:
                results["native_rust_gateway"] = {"error": "gateway did not become ready"}
        else:
            results["native_rust_gateway"] = {"error": f"binary not found: {gw_bin} (run make native-rust-build)"}

        # --- Python FastAPI (uvicorn) ---
        py = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "tryops.api:create_app", "--factory",
             "--host", "127.0.0.1", "--port", str(args.python_port), "--log-level", "warning"],
            cwd=str(ROOT), env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(py)
        py_url = f"http://127.0.0.1:{args.python_port}/health"
        if _wait_ready(py_url):
            run_load(py_url, total_requests=200, concurrency=8)  # warmup
            results["python_fastapi"] = run_load(
                py_url, total_requests=args.requests, concurrency=args.concurrency
            )
        else:
            results["python_fastapi"] = {"error": "uvicorn did not become ready"}
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()

    speedup = None
    n = results.get("native_rust_gateway", {})
    p = results.get("python_fastapi", {})
    if n.get("requests_per_sec") and p.get("requests_per_sec"):
        speedup = {
            "throughput_x": round(n["requests_per_sec"] / p["requests_per_sec"], 2),
            "p99_latency_x": round(p["latency_ms"]["p99"] / max(n["latency_ms"]["p99"], 1e-6), 2),
        }

    report = {
        "schema_version": "tryops.gateway_benchmark.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "load": {"requests": args.requests, "concurrency": args.concurrency, "endpoint": "/health"},
        "results": results,
        "native_speedup": speedup,
        "note": "Identical /health handler; measures pure serving-runtime overhead "
                "(Rust+Tokio+Axum vs Python+uvicorn+FastAPI).",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    for name, r in results.items():
        if r.get("requests_per_sec"):
            lm = r["latency_ms"]
            print(f"{name:>22}: {r['requests_per_sec']:>9.0f} req/s  "
                  f"p50={lm['p50']:.2f}ms p99={lm['p99']:.2f}ms  errors={r['errors']}")
        else:
            print(f"{name:>22}: {r.get('error')}")
    if speedup:
        print(f"native speedup: {speedup['throughput_x']}x throughput, {speedup['p99_latency_x']}x lower p99")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
