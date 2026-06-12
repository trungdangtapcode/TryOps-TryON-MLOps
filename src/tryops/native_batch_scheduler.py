"""Bridge to the native C++ continuous-batching scheduler benchmark."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NATIVE_BATCH_SCHEDULER_CLI = Path("artifacts/native/tryops_batch_scheduler_cli")


def evaluate_with_native_batch_scheduler(
    requests: Sequence[dict[str, Any]],
    *,
    max_num_seqs: int = 4,
    prefill_token_ms: float = 0.01,
    decode_step_ms: float = 0.18,
    batch_growth_factor: float = 0.08,
    static_batch_wait_ms: float = 0.0,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compare static batching with continuous batching in the native C++ engine."""

    if not requests:
        raise ValueError("requests cannot be empty")

    cli = Path(
        cli_path
        or os.environ.get("TRYOPS_NATIVE_BATCH_SCHEDULER_CLI", DEFAULT_NATIVE_BATCH_SCHEDULER_CLI)
    )
    if not cli.exists():
        return {
            "schema_version": "tryops.native_batch_scheduler.v1",
            "engine": "native_cpp_iteration_scheduler",
            "available": False,
            "cli_path": str(cli),
            "reason": "native batch scheduler CLI not found",
        }

    payload = serialize_scheduler_payload(
        requests,
        max_num_seqs=max_num_seqs,
        prefill_token_ms=prefill_token_ms,
        decode_step_ms=decode_step_ms,
        batch_growth_factor=batch_growth_factor,
        static_batch_wait_ms=static_batch_wait_ms,
    )
    completed = subprocess.run(
        [str(cli)],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return {
            "schema_version": "tryops.native_batch_scheduler.v1",
            "engine": "native_cpp_iteration_scheduler",
            "available": True,
            "cli_path": str(cli),
            "returncode": completed.returncode,
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }

    result = json.loads(completed.stdout)
    result["available"] = True
    result["cli_path"] = str(cli)
    result["returncode"] = completed.returncode
    return result


def serialize_scheduler_payload(
    requests: Sequence[dict[str, Any]],
    *,
    max_num_seqs: int = 4,
    prefill_token_ms: float = 0.01,
    decode_step_ms: float = 0.18,
    batch_growth_factor: float = 0.08,
    static_batch_wait_ms: float = 0.0,
) -> str:
    """Serialize a request stream to the line protocol consumed by the C++ CLI."""

    if max_num_seqs < 1:
        raise ValueError("max_num_seqs must be at least 1")
    arrivals: list[float] = []
    prefills: list[float] = []
    decodes: list[int] = []
    for request in requests:
        arrivals.append(float(request["arrival_ms"]))
        prefill = float(request["prefill_tokens"])
        decode = int(request["decode_tokens"])
        if prefill < 0:
            raise ValueError("prefill_tokens must be non-negative")
        if decode < 1:
            raise ValueError("decode_tokens must be positive")
        prefills.append(prefill)
        decodes.append(decode)

    lines = [
        f"request.arrival_ms={_csv(arrivals)}",
        f"request.prefill_tokens={_csv(prefills)}",
        f"request.decode_tokens={_csv(decodes)}",
        f"config.max_num_seqs={int(max_num_seqs)}",
        f"config.prefill_token_ms={float(prefill_token_ms)}",
        f"config.decode_step_ms={float(decode_step_ms)}",
        f"config.batch_growth_factor={float(batch_growth_factor)}",
        f"config.static_batch_wait_ms={float(static_batch_wait_ms)}",
    ]
    return "\n".join(lines) + "\n"


def _csv(values: Sequence[float | int]) -> str:
    return ",".join(str(value) for value in values)
