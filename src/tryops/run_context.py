from __future__ import annotations

import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def build_run_context(
    *,
    run_name: str,
    run_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Build reproducibility metadata for local pipeline and benchmark runs."""

    return {
        "schema_version": "tryops.run_context.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "run_name": run_name,
        "run_id": run_id or f"run-{uuid4()}",
        "trace_id": trace_id or f"trace-{uuid4()}",
        "code": detect_code_version(),
        "environment": environment_details(),
        "hardware": hardware_details(),
    }


def detect_code_version() -> dict[str, str]:
    explicit = os.environ.get("TRYOPS_CODE_VERSION") or os.environ.get("GITHUB_SHA")
    if explicit:
        return {"version": explicit, "source": "environment"}

    git_head = Path(".git/HEAD")
    if git_head.exists():
        try:
            head = git_head.read_text(encoding="utf-8").strip()
        except OSError:
            head = ""
        if head.startswith("ref: "):
            ref_path = Path(".git") / head.removeprefix("ref: ").strip()
            if ref_path.exists():
                try:
                    return {"version": ref_path.read_text(encoding="utf-8").strip(), "source": "git-ref"}
                except OSError:
                    pass
        if head:
            return {"version": head, "source": "git-head"}

    return {
        "version": "local-dev-unversioned",
        "source": "not-a-git-repository",
    }


def environment_details() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
    }


def hardware_details() -> dict[str, Any]:
    memory_gb = _linux_memory_gb()
    return {
        "cpu_count": os.cpu_count() or 0,
        "processor": platform.processor() or "unknown",
        "machine": platform.machine(),
        "memory_gb": memory_gb,
    }


def _linux_memory_gb() -> float | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    try:
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                parts = line.split()
                if len(parts) >= 2:
                    return round(int(parts[1]) / (1024.0 * 1024.0), 3)
    except OSError:
        return None
    return None
