from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Callable
from uuid import uuid4


JobRunner = Callable[[dict[str, Any]], dict[str, Any]]
JobUpdateCallback = Callable[[dict[str, Any]], None]
ACTIVE_JOB_STATUSES = {"queued", "running"}


class JobConcurrencyLimitExceeded(Exception):
    def __init__(self, *, workload: str, account_id: str | None, active: int, limit: int) -> None:
        self.workload = workload
        self.account_id = account_id
        self.active = active
        self.limit = limit
        super().__init__(f"{workload} active job limit reached: {active}/{limit}")


@dataclass
class JobRecord:
    job_id: str
    workload: str
    request_id: str
    status: str
    created_at: str
    queued_at: str
    account_id: str | None = None
    principal_subject: str | None = None
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
            "account_id": self.account_id,
            "principal_subject": self.principal_subject,
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
        self.max_workers = max_workers
        self._records: dict[str, JobRecord] = {}
        self._lock = Lock()

    def submit(
        self,
        *,
        workload: str,
        request_id: str,
        payload: dict[str, Any],
        runner: JobRunner,
        account_id: str | None = None,
        principal_subject: str | None = None,
        active_limit: int | None = None,
        payload_metadata: dict[str, Any] | None = None,
        on_update: JobUpdateCallback | None = None,
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
            account_id=account_id,
            principal_subject=principal_subject,
            payload_metadata=payload_metadata or {},
        )
        with self._lock:
            if active_limit is not None:
                active = self.active_count_locked(account_id=account_id, workload=workload)
                if active >= active_limit:
                    raise JobConcurrencyLimitExceeded(
                        workload=workload,
                        account_id=account_id,
                        active=active,
                        limit=active_limit,
                    )
            self._records[job_id] = record
            queue_depth = self.queue_depth_locked()
            queued_snapshot = record.to_dict(include_result=False)
        _notify_job_update(on_update, queued_snapshot)
        runner_payload = deepcopy(payload)
        runner_payload.setdefault("job_id", job_id)
        self._executor.submit(self._run, job_id, runner_payload, runner, on_update)
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

    def active_count(self, *, account_id: str | None = None, workload: str | None = None) -> int:
        with self._lock:
            return self.active_count_locked(account_id=account_id, workload=workload)

    def list(
        self,
        *,
        account_id: str | None = None,
        workload: str | None = None,
        statuses: set[str] | None = None,
        include_result: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 100))
        with self._lock:
            records = []
            for record in self._records.values():
                if account_id is not None and record.account_id != account_id:
                    continue
                if workload is not None and record.workload != workload:
                    continue
                if statuses is not None and record.status not in statuses:
                    continue
                records.append(record.to_dict(include_result=include_result))
            records.sort(key=lambda item: str(item["created_at"]), reverse=True)
            return records[:bounded_limit]

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
        return self.active_count_locked()

    def active_count_locked(self, *, account_id: str | None = None, workload: str | None = None) -> int:
        count = 0
        for record in self._records.values():
            if record.status not in ACTIVE_JOB_STATUSES:
                continue
            if account_id is not None and record.account_id != account_id:
                continue
            if workload is not None and record.workload != workload:
                continue
            count += 1
        return count

    def _run(
        self,
        job_id: str,
        payload: dict[str, Any],
        runner: JobRunner,
        on_update: JobUpdateCallback | None = None,
    ) -> None:
        with self._lock:
            record = self._records[job_id]
            record.status = "running"
            record.started_at = _now()
            running_snapshot = record.to_dict(include_result=False)
        _notify_job_update(on_update, running_snapshot)
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
                completed_snapshot = record.to_dict(include_result=True)
            _notify_job_update(on_update, completed_snapshot)
        except Exception as exc:  # pragma: no cover - defensive job boundary
            with self._lock:
                record = self._records[job_id]
                record.status = "failed"
                record.completed_at = _now()
                record.error = {"code": "job_exception", "message": str(exc)}
                failed_snapshot = record.to_dict(include_result=True)
            _notify_job_update(on_update, failed_snapshot)


def _notify_job_update(callback: JobUpdateCallback | None, snapshot: dict[str, Any]) -> None:
    if callback is None:
        return
    try:
        callback(deepcopy(snapshot))
    except Exception:
        # Job execution must not die because the durability side-channel failed.
        return


def _env_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


VTON_JOB_QUEUE = InMemoryJobQueue(max_workers=_env_int("TRYOPS_VTON_JOB_WORKERS", default=1, minimum=1, maximum=16))


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
