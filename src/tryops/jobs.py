from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Callable
from uuid import uuid4


JobRunner = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class JobRecord:
    job_id: str
    workload: str
    request_id: str
    status: str
    created_at: str
    queued_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    payload_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_result: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "tryops.job.v1",
            "job_id": self.job_id,
            "workload": self.workload,
            "request_id": self.request_id,
            "status": self.status,
            "created_at": self.created_at,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "payload_metadata": deepcopy(self.payload_metadata),
        }
        if self.error is not None:
            payload["error"] = deepcopy(self.error)
        if include_result and self.result is not None:
            payload["result"] = deepcopy(self.result)
        return payload


class InMemoryJobQueue:
    def __init__(self, *, max_workers: int = 1) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tryops-job")
        self._records: dict[str, JobRecord] = {}
        self._lock = Lock()

    def submit(
        self,
        *,
        workload: str,
        request_id: str,
        payload: dict[str, Any],
        runner: JobRunner,
        payload_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        job_id = f"job-{uuid4()}"
        now = _now()
        record = JobRecord(
            job_id=job_id,
            workload=workload,
            request_id=request_id,
            status="queued",
            created_at=now,
            queued_at=now,
            payload_metadata=payload_metadata or {},
        )
        with self._lock:
            self._records[job_id] = record
            queue_depth = self.queue_depth_locked()
        self._executor.submit(self._run, job_id, deepcopy(payload), runner)
        accepted = record.to_dict(include_result=False)
        accepted["status"] = "accepted"
        accepted["queue_depth"] = queue_depth
        return accepted

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                return None
            snapshot = record.to_dict()
            snapshot["queue_depth"] = self.queue_depth_locked()
            return snapshot

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            records = [record.to_dict(include_result=False) for record in self._records.values()]
            return {
                "schema_version": "tryops.job_queue.v1",
                "queue_depth": self.queue_depth_locked(),
                "records": sorted(records, key=lambda item: str(item["created_at"])),
            }

    def queue_depth(self) -> int:
        with self._lock:
            return self.queue_depth_locked()

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    def queue_depth_locked(self) -> int:
        return sum(1 for record in self._records.values() if record.status in {"queued", "running"})

    def _run(self, job_id: str, payload: dict[str, Any], runner: JobRunner) -> None:
        with self._lock:
            record = self._records[job_id]
            record.status = "running"
            record.started_at = _now()
        try:
            result = runner(payload)
            status = "completed" if result.get("status") == "completed" else "failed"
            with self._lock:
                record = self._records[job_id]
                record.status = status
                record.result = deepcopy(result)
                record.completed_at = _now()
                if status == "failed":
                    record.error = deepcopy(result.get("error", {"code": "job_failed"}))
        except Exception as exc:  # pragma: no cover - defensive job boundary
            with self._lock:
                record = self._records[job_id]
                record.status = "failed"
                record.completed_at = _now()
                record.error = {"code": "job_exception", "message": str(exc)}


VTON_JOB_QUEUE = InMemoryJobQueue(max_workers=1)


def render_job_metrics() -> str:
    return (
        "# HELP tryops_async_job_queue_depth Current queued or running async jobs.\n"
        "# TYPE tryops_async_job_queue_depth gauge\n"
        f'tryops_async_job_queue_depth{{workload="vton"}} {VTON_JOB_QUEUE.queue_depth()}\n'
    )


def reset_job_queue() -> None:
    VTON_JOB_QUEUE.reset()


def _now() -> str:
    return datetime.now(UTC).isoformat()
