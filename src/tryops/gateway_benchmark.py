"""Head-to-head serving benchmark: native Rust gateway vs Python FastAPI.

Quantifies the platform thesis ("Python is the lab layer, not the production
boundary") with measured numbers — requests/sec and p50/p95/p99 latency on the
identical ``/health`` handler served by the compiled Rust+Tokio+Axum gateway and
by Python+uvicorn+FastAPI. The load driver is stdlib-only; the math is pure and
unit-tested.
"""

from __future__ import annotations

import http.client
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any
from urllib.parse import urlparse


def summarize_latencies(
    latencies_ms: list[float], *, elapsed_s: float, errors: int, total: int
) -> dict[str, Any]:
    """Aggregate raw latencies into throughput + percentile summary (pure)."""

    ok = sorted(latencies_ms)
    n = len(ok)

    def pct(q: float) -> float:
        if not ok:
            return 0.0
        idx = min(n - 1, max(0, round((n - 1) * q)))
        return round(ok[idx], 4)

    return {
        "requests": total,
        "errors": errors,
        "elapsed_s": round(elapsed_s, 6),
        "requests_per_sec": round(total / elapsed_s, 2) if elapsed_s > 0 else 0.0,
        "latency_ms": {
            "p50": pct(0.50),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "min": round(ok[0], 4) if ok else 0.0,
            "max": round(ok[-1], 4) if ok else 0.0,
            "mean": round(sum(ok) / n, 4) if ok else 0.0,
        },
    }


def _worker(host: str, port: int, path: str, n: int, timeout: float) -> tuple[list[float], int]:
    """One persistent keep-alive connection issuing ``n`` sequential requests —
    this is how wrk/ab measure: connection setup is paid once, so the result
    reflects server throughput, not TCP-handshake overhead."""

    lat: list[float] = []
    errs = 0
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    for _ in range(n):
        start = perf_counter()
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            resp.read()
            if resp.status != 200:
                errs += 1
            else:
                lat.append((perf_counter() - start) * 1000.0)
        except Exception:
            errs += 1
            try:
                conn.close()
                conn = http.client.HTTPConnection(host, port, timeout=timeout)
            except Exception:
                pass
    conn.close()
    return lat, errs


def run_load(
    url: str, *, total_requests: int = 2000, concurrency: int = 32, timeout: float = 5.0
) -> dict[str, Any]:
    """Drive ``total_requests`` over ``concurrency`` persistent (keep-alive)
    connections and summarize throughput + latency percentiles."""

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    per_worker = max(1, total_requests // concurrency)
    actual_total = per_worker * concurrency

    latencies_ms: list[float] = []
    errors = 0
    started = perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(_worker, host, port, path, per_worker, timeout)
            for _ in range(concurrency)
        ]
        for fut in futures:
            lat, errs = fut.result()
            latencies_ms.extend(lat)
            errors += errs
    elapsed_s = max(perf_counter() - started, 1e-9)
    return summarize_latencies(
        latencies_ms, elapsed_s=elapsed_s, errors=errors, total=actual_total
    )
