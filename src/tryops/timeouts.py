from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from time import perf_counter
from typing import Any, Callable, TypeVar


T = TypeVar("T")


class RequestTimeoutError(TimeoutError):
    def __init__(self, *, timeout_ms: int, elapsed_ms: float) -> None:
        self.timeout_ms = timeout_ms
        self.elapsed_ms = elapsed_ms
        super().__init__(f"request exceeded timeout_ms={timeout_ms}")


def run_with_timeout(
    operation: Callable[[], T],
    *,
    timeout_ms: int,
    operation_name: str = "operation",
) -> T:
    if timeout_ms < 1:
        raise ValueError("timeout_ms must be positive")

    started = perf_counter()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"tryops-{operation_name}")
    future = executor.submit(operation)
    try:
        result = future.result(timeout=timeout_ms / 1000.0)
        executor.shutdown(wait=True, cancel_futures=False)
        return result
    except FutureTimeoutError as exc:
        elapsed_ms = (perf_counter() - started) * 1000.0
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise RequestTimeoutError(timeout_ms=timeout_ms, elapsed_ms=elapsed_ms) from exc


def timeout_details(exc: RequestTimeoutError) -> list[dict[str, Any]]:
    return [
        {
            "field": "timeout_ms",
            "message": f"request exceeded timeout_ms={exc.timeout_ms}",
            "timeout_ms": exc.timeout_ms,
            "elapsed_ms": round(exc.elapsed_ms, 3),
        }
    ]
