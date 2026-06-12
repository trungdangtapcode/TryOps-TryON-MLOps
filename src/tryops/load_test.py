from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

from tryops.pipelines.llm_baseline import generate_baseline_response
from tryops.run_context import build_run_context


def run_llm_load_test(
    *,
    prompt: str,
    concurrency: int,
    requests: int,
    output_path: str | Path,
    model_alias: str = "baseline",
) -> dict[str, Any]:
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    if requests < 1:
        raise ValueError("requests must be at least 1")

    run_context = build_run_context(run_name="llm-local-load-test")
    started = perf_counter()
    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(_single_request, index, prompt, model_alias)
            for index in range(requests)
        ]
        for future in as_completed(futures):
            records.append(future.result())

    wall_ms = round((perf_counter() - started) * 1000.0, 3)
    latencies = [record["latency_ms"] for record in records]
    output_tokens = sum(record["output_tokens"] for record in records)
    report = {
        "schema_version": "tryops.llm_load_test.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "run_context": run_context,
        "model_alias": model_alias,
        "concurrency": concurrency,
        "requests": requests,
        "records": sorted(records, key=lambda item: item["index"]),
        "summary": {
            "wall_ms": wall_ms,
            "latency_avg_ms": round(mean(latencies), 6),
            "latency_p95_ms": _percentile(latencies, 0.95),
            "requests_per_second": round(requests / max(wall_ms / 1000.0, 0.001), 6),
            "output_tokens_per_second": round(output_tokens / max(wall_ms / 1000.0, 0.001), 6),
        },
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _single_request(index: int, prompt: str, model_alias: str) -> dict[str, Any]:
    started = perf_counter()
    response = generate_baseline_response(prompt=prompt, model_alias=model_alias, structured=False)
    wall_ms = round((perf_counter() - started) * 1000.0, 3)
    return {
        "index": index,
        "status": response["status"],
        "latency_ms": wall_ms,
        "model_latency_ms": response["metrics"]["latency_ms"],
        "tokens_per_second": response["metrics"]["tokens_per_second"],
        "output_tokens": response["output"]["estimated_tokens"],
        "safety_status": response["safety"]["status"],
    }


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return round(float(ordered[index]), 6)
