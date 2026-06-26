#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import io
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.image_metrics import compare_images  # noqa: E402
from tryops.simple_image import RgbImage  # noqa: E402
from tryops.system_benchmark import (  # noqa: E402
    SCHEMA_VERSION,
    build_system_benchmark_report,
    discover_vton_dataset_pairs,
    write_benchmark_artifacts,
)


DEFAULT_EXPERIMENT = "tryops-vton-benchmark"


class MlflowRestClient:
    def __init__(self, tracking_uri: str) -> None:
        self.tracking_uri = tracking_uri.rstrip("/")

    def ensure_experiment(self, name: str) -> str:
        existing = self._post("/api/2.0/mlflow/experiments/search", {"max_results": 1000})
        for experiment in existing.get("experiments", []):
            if isinstance(experiment, dict) and experiment.get("name") == name:
                return str(experiment["experiment_id"])
        created = self._post("/api/2.0/mlflow/experiments/create", {"name": name})
        return str(created["experiment_id"])

    def start_run(self, *, experiment_id: str, run_name: str, tags: dict[str, str]) -> str:
        payload = {
            "experiment_id": experiment_id,
            "start_time": _now_ms(),
            "tags": [{"key": "mlflow.runName", "value": run_name}]
            + [{"key": key, "value": value} for key, value in sorted(tags.items())],
        }
        response = self._post("/api/2.0/mlflow/runs/create", payload)
        return str(response["run"]["info"]["run_id"])

    def log_batch(
        self,
        *,
        run_id: str,
        metrics: dict[str, float],
        params: dict[str, str],
        tags: dict[str, str] | None = None,
    ) -> None:
        timestamp = _now_ms()
        payload = {
            "run_id": run_id,
            "metrics": [
                {"key": key, "value": float(value), "timestamp": timestamp, "step": 0}
                for key, value in sorted(metrics.items())
            ],
            "params": [{"key": key, "value": value[:500]} for key, value in sorted(params.items())],
            "tags": [{"key": key, "value": value[:5000]} for key, value in sorted((tags or {}).items())],
        }
        self._post("/api/2.0/mlflow/runs/log-batch", payload)

    def end_run(self, *, run_id: str, status: str = "FINISHED") -> None:
        self._post(
            "/api/2.0/mlflow/runs/update",
            {"run_id": run_id, "status": status, "end_time": _now_ms()},
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._get("/api/2.0/mlflow/runs/get", {"run_id": run_id})

    def _get(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        url = f"{self.tracking_uri}{path}?{urllib.parse.urlencode(query)}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"MLflow request failed ({exc.code}) {path}: {detail}") from exc
        except OSError as exc:
            raise RuntimeError(f"MLflow is not reachable at {self.tracking_uri}: {exc}") from exc
        return _parse_json_object(body)

    def _post(self, path: str, payload: dict[str, Any], *, allow_404: bool = False) -> dict[str, Any]:
        url = f"{self.tracking_uri}{path}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if allow_404 and exc.code == 404:
                return {}
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"MLflow request failed ({exc.code}) {path}: {detail}") from exc
        except OSError as exc:
            raise RuntimeError(f"MLflow is not reachable at {self.tracking_uri}: {exc}") from exc
        if not body.strip():
            return {}
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError(f"MLflow returned non-object JSON from {path}")
        return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark live TryOps VTON jobs from data/ and log metrics to MLflow."
    )
    parser.add_argument("--base-url", default=os.getenv("TRYOPS_STACK_GATEWAY_URL", "http://127.0.0.1:18081"))
    parser.add_argument("--mlflow-uri", default=os.getenv("TRYOPS_STACK_MLFLOW_URL", "http://127.0.0.1:15000"))
    parser.add_argument("--experiment", default=os.getenv("TRYOPS_BENCHMARK_EXPERIMENT", DEFAULT_EXPERIMENT))
    parser.add_argument("--api-key", default=os.getenv("TRYOPS_BENCHMARK_API_KEY", os.getenv("TRYOPS_SMOKE_API_KEY", "tryops-admin-demo-key")))
    parser.add_argument("--workloads", default=os.getenv("TRYOPS_BENCHMARK_WORKLOADS", "vton"))
    parser.add_argument("--requests", type=int, default=int(os.getenv("TRYOPS_BENCHMARK_REQUESTS", "3")))
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("TRYOPS_BENCHMARK_CONCURRENCY", "1")))
    parser.add_argument("--vton-requests", type=int, default=int(os.getenv("TRYOPS_BENCHMARK_VTON_REQUESTS", "1")))
    parser.add_argument("--vton-model-alias", default=os.getenv("TRYOPS_BENCHMARK_VTON_ALIAS", "champion"))
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("TRYOPS_BENCHMARK_DATA_DIR", "data")))
    parser.add_argument("--person-image", type=Path, default=_optional_path_env("TRYOPS_BENCHMARK_PERSON_IMAGE"))
    parser.add_argument("--garment-image", type=Path, default=_optional_path_env("TRYOPS_BENCHMARK_GARMENT_IMAGE"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/eval/vton_benchmark"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/vton_benchmark_report.md"))
    parser.add_argument("--fail-on-errors", action="store_true")
    args = parser.parse_args()

    if args.requests < 1:
        raise SystemExit("--requests must be at least 1")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")
    if args.vton_requests < 0:
        raise SystemExit("--vton-requests must be at least 0")
    if (args.person_image is None) != (args.garment_image is None):
        raise SystemExit("--person-image and --garment-image must be provided together")

    base_url = args.base_url.rstrip("/")
    mlflow_uri = args.mlflow_uri.rstrip("/")
    workloads = _parse_workloads(args.workloads)
    _wait_for_stack(base_url)
    mlflow = MlflowRestClient(mlflow_uri)
    experiment_id = mlflow.ensure_experiment(args.experiment)

    records: list[dict[str, Any]] = []
    if "health" in workloads:
        records.extend(
            _run_concurrent(
                count=args.requests,
                concurrency=args.concurrency,
                worker=lambda index: _run_health_probe(base_url, index=index),
            )
        )
    if "vton" in workloads and args.vton_requests:
        vton_pairs = _select_vton_pairs(
            data_dir=args.data_dir,
            limit=args.vton_requests,
            person_image=args.person_image,
            garment_image=args.garment_image,
        )
        records.extend(
            _run_vton_pairs_concurrent(
                base_url,
                api_key=args.api_key,
                pairs=vton_pairs,
                concurrency=args.concurrency,
                model_alias=args.vton_model_alias,
            )
        )

    config = {
        "base_url": base_url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "vton_requests": args.vton_requests,
        "workloads": sorted(workloads),
        "vton_model_alias": args.vton_model_alias,
        "data_dir": str(args.data_dir),
        "person_image_override": str(args.person_image) if args.person_image is not None else "",
        "garment_image_override": str(args.garment_image) if args.garment_image is not None else "",
    }
    mlflow_info = {
        "tracking_uri": mlflow_uri,
        "experiment_name": args.experiment,
        "experiment_id": experiment_id,
        "experiment_url": f"{mlflow_uri}/#/experiments/{experiment_id}",
        "run_ids": [],
    }
    report = build_system_benchmark_report(records=records, mlflow=mlflow_info, config=config)
    paths = write_benchmark_artifacts(report=report, output_dir=args.output_dir, report_path=args.report)
    run_refs = _log_summary_to_mlflow(
        mlflow,
        experiment_id=experiment_id,
        experiment_name=args.experiment,
        summary=report["summary"],
        paths=paths,
        config=config,
    )
    report["mlflow"]["run_ids"] = [str(run_ref["run_id"]) for run_ref in run_refs]
    paths = write_benchmark_artifacts(report=report, output_dir=args.output_dir, report_path=args.report)
    artifact_results = _log_artifacts_to_mlflow(
        mlflow,
        run_refs=run_refs,
        records=records,
        paths=paths,
        base_url=base_url,
        api_key=args.api_key,
    )
    for run_ref in run_refs:
        mlflow.end_run(run_id=str(run_ref["run_id"]))
    report["mlflow"]["artifact_uploads"] = artifact_results
    paths = write_benchmark_artifacts(report=report, output_dir=args.output_dir, report_path=args.report)

    print(f"MLflow experiment: {mlflow_info['experiment_url']}")
    print(f"JSON report:        {paths['json']}")
    print(f"Summary CSV:        {paths['summary_csv']}")
    print(f"Markdown report:    {paths['markdown']}")
    _print_summary_table(report["summary"])

    if args.fail_on_errors and any(float(row.get("error_rate_percent") or 0.0) > 0.0 for row in report["summary"]):
        return 2
    return 0


def _parse_workloads(raw: str) -> set[str]:
    workloads = {item.strip().lower() for item in raw.split(",") if item.strip()}
    allowed = {"health", "vton"}
    invalid = sorted(workloads - allowed)
    if invalid:
        raise SystemExit(f"unsupported workload(s): {', '.join(invalid)}")
    if not workloads:
        raise SystemExit("at least one workload is required")
    return workloads


def _select_vton_pairs(
    *,
    data_dir: Path,
    limit: int,
    person_image: Path | None,
    garment_image: Path | None,
) -> list[dict[str, str]]:
    if person_image is not None and garment_image is not None:
        return [
            {
                "pair_id": f"override-{index + 1:04d}",
                "person_image": str(person_image),
                "garment_image": str(garment_image),
            }
            for index in range(limit)
        ]
    return discover_vton_dataset_pairs(data_dir, limit=limit)


def _run_concurrent(*, count: int, concurrency: int, worker: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker, index) for index in range(count)]
        for future in as_completed(futures):
            records.append(future.result())
    return sorted(records, key=lambda item: int(item.get("index", 0)))


def _run_vton_pairs_concurrent(
    base_url: str,
    *,
    api_key: str,
    pairs: list[dict[str, str]],
    concurrency: int,
    model_alias: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    workers = max(1, min(concurrency, len(pairs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _run_vton_job,
                base_url,
                api_key=api_key,
                index=index,
                person_image=Path(pair["person_image"]),
                garment_image=Path(pair["garment_image"]),
                pair_id=pair["pair_id"],
                model_alias=model_alias,
            )
            for index, pair in enumerate(pairs)
        ]
        for future in as_completed(futures):
            records.extend(future.result())
    return sorted(records, key=lambda item: (int(item.get("index", 0)), str(item.get("scenario", ""))))


def _wait_for_stack(base_url: str) -> None:
    last = ""
    for _ in range(60):
        status, body, error = _request_json("GET", f"{base_url}/api/ready")
        if status == 200 and body.get("status") == "ready":
            return
        last = error or json.dumps(body, sort_keys=True)[:500]
        time.sleep(1)
    raise SystemExit(f"TryOps stack is not ready at {base_url}: {last}")


def _run_health_probe(base_url: str, *, index: int) -> dict[str, Any]:
    started = _now_ms()
    status, body, error = _request_json("GET", f"{base_url}/api/health")
    ended = _now_ms()
    ok = status == 200 and body.get("status") == "ok"
    return {
        "workload": "gateway",
        "scenario": "gateway_health",
        "target": "rust_gateway_api",
        "index": index,
        "ok": ok,
        "status": "completed" if ok else "failed",
        "http_status": status,
        "latency_ms": ended - started,
        "started_epoch_ms": started,
        "ended_epoch_ms": ended,
        "request_id": "",
        "error_code": "" if ok else "health_probe_failed",
        "error_message": "" if ok else (error or str(body)[:250]),
        "metrics": {},
    }


def _run_vton_job(
    base_url: str,
    *,
    api_key: str,
    index: int,
    person_image: Path,
    garment_image: Path,
    pair_id: str,
    model_alias: str,
) -> list[dict[str, Any]]:
    if not person_image.exists():
        raise SystemExit(f"person image does not exist: {person_image}")
    if not garment_image.exists():
        raise SystemExit(f"garment image does not exist: {garment_image}")
    system_samples = [_capture_system_snapshot()]
    records: list[dict[str, Any]] = []
    person = _upload_vton_image(base_url, api_key=api_key, index=index, role="person", path=person_image)
    garment = _upload_vton_image(base_url, api_key=api_key, index=index, role="garment", path=garment_image)
    records.extend([person["record"], garment["record"]])
    if not person["record"]["ok"] or not garment["record"]["ok"]:
        records.append(_failed_vton_record(index=index, message="VTON upload failed; inference was not submitted."))
        return records

    request_id = f"req-benchmark-vton-{uuid4()}"
    payload = {
        "api_key": api_key,
        "request_id": request_id,
        "person_image_path": person["artifact_path"],
        "garment_image_path": garment["artifact_path"],
        "output_image_path": f"artifacts/runtime/vton/system-benchmark/{request_id}.png",
        "model_alias": model_alias,
        "user_id": "system-benchmark",
        "quota_plan": "team",
        "category": "tops",
        "garment_photo_type": "model",
        "num_timesteps": 30,
        "guidance_scale": 1.5,
        "seed": 555,
        "segmentation_free": True,
        "timeout_ms": 300000,
    }
    started = _now_ms()
    status, accepted, error = _request_json("POST", f"{base_url}/api/vton/jobs", payload)
    job_id = str(accepted.get("job_id") or "")
    if status != 200 or not job_id:
        ended = _now_ms()
        records.append(
            {
                "workload": "vton",
                "scenario": "vton_job_real",
                "target": f"{model_alias}:{pair_id}",
                "index": index,
                "ok": False,
                "status": "failed",
                "http_status": status,
                "latency_ms": ended - started,
                "started_epoch_ms": started,
                "ended_epoch_ms": ended,
                "request_id": request_id,
                "error_code": _error_code(accepted, "vton_job_submit_failed"),
                "error_message": _error_message(accepted, error),
                "metrics": {},
            }
        )
        return records
    final = _poll_vton_job(base_url, api_key=api_key, job_id=job_id, timeout_s=320.0)
    system_samples.extend(final.get("system_samples", []))
    system_samples.append(_capture_system_snapshot())
    ended = _now_ms()
    body = final["body"]
    result = body.get("result", {}) if isinstance(body.get("result"), dict) else {}
    report = result.get("report", {}) if isinstance(result.get("report"), dict) else {}
    metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
    native_vton = result.get("native_vton", {}) if isinstance(result.get("native_vton"), dict) else {}
    ok = final["status"] == 200 and body.get("status") == "completed" and result.get("status") == "completed"
    output_path = _nested_text(report, ["output", "path"])
    quality_metrics = (
        _compute_ground_truth_image_metrics(
            base_url=base_url,
            api_key=api_key,
            ground_truth_path=person_image,
            output_path=output_path,
        )
        if ok
        else {}
    )
    records.append(
        {
            "workload": "vton",
            "scenario": "vton_job_real",
            "target": _nested_text(report, ["model", "name"]) or f"{model_alias}:{pair_id}",
            "index": index,
            "ok": ok,
            "status": str(body.get("status") or result.get("status") or "failed"),
            "http_status": final["status"],
            "latency_ms": ended - started,
            "started_epoch_ms": started,
            "ended_epoch_ms": ended,
            "request_id": str(body.get("request_id") or request_id),
            "pair_id": pair_id,
            "error_code": "" if ok else (_error_code(body, "") or _error_code(result, "vton_job_failed")),
            "error_message": "" if ok else (_error_message(body, "") or _error_message(result, final["error"])),
            "ground_truth_path": str(person_image),
            "garment_path": str(garment_image),
            "person_artifact_path": person["artifact_path"],
            "garment_artifact_path": garment["artifact_path"],
            "output_path": output_path,
            "system_samples": system_samples,
            "metrics": {
                "model_latency_ms": _float(metrics.get("latency_ms")),
                "quality_score": _float(metrics.get("native_quality_score") or native_vton.get("quality_score")),
                "gpu_memory_gb": _float(metrics.get("peak_vram_gb") or metrics.get("gpu_memory_gb")),
                "cost_usd": _float(metrics.get("estimated_cost_usd")),
                **_system_metrics_from_samples(system_samples),
                **quality_metrics,
            },
        }
    )
    return records


def _upload_vton_image(
    base_url: str,
    *,
    api_key: str,
    index: int,
    role: str,
    path: Path,
) -> dict[str, Any]:
    request_id = f"req-benchmark-upload-{role}-{uuid4()}"
    source_bytes = path.read_bytes()
    data = _png_upload_bytes(path, source_bytes)
    payload = {
        "api_key": api_key,
        "request_id": request_id,
        "role": role,
        "filename": f"{path.stem}.png",
        "data_url": f"data:image/png;base64,{base64.b64encode(data).decode('ascii')}",
    }
    started = _now_ms()
    status, body, error = _request_json("POST", f"{base_url}/api/vton/upload", payload)
    ended = _now_ms()
    artifact_path = str(_nested_text(body, ["data", "path"]) or "")
    ok = status == 200 and body.get("status") == "uploaded" and artifact_path.startswith("artifact:")
    return {
        "artifact_path": artifact_path,
        "record": {
            "workload": "vton",
            "scenario": "vton_upload_input",
            "target": "minio_runtime_artifacts",
            "index": index,
            "role": role,
            "source_path": str(path),
            "artifact_path": artifact_path,
            "ok": ok,
            "status": str(body.get("status") or ("completed" if ok else "failed")),
            "http_status": status,
            "latency_ms": ended - started,
            "started_epoch_ms": started,
            "ended_epoch_ms": ended,
            "request_id": str(body.get("request_id") or request_id),
            "error_code": "" if ok else _error_code(body, "vton_upload_failed"),
            "error_message": "" if ok else _error_message(body, error),
            "metrics": {"input_bytes": float(len(source_bytes)), "upload_png_bytes": float(len(data))},
        },
    }


def _png_upload_bytes(path: Path, source_bytes: bytes) -> bytes:
    if source_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return source_bytes
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            f"{path} is not PNG. Install Pillow or pass PNG files with --person-image/--garment-image."
        ) from exc
    with Image.open(io.BytesIO(source_bytes)) as image:
        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return output.getvalue()


def _compute_ground_truth_image_metrics(
    *,
    base_url: str,
    api_key: str,
    ground_truth_path: Path,
    output_path: str,
) -> dict[str, float | str]:
    if not output_path:
        return {"image_metric_error": "missing VTON output path"}
    try:
        reference = _rgb_image_from_bytes(ground_truth_path.read_bytes())
        candidate = _rgb_image_from_bytes(_read_output_image_bytes(base_url, api_key=api_key, output_path=output_path))
        metrics = compare_images(reference, candidate)
        return {
            "ssim": float(metrics["global_ssim_luma"]),
            "psnr": float(metrics["psnr"]),
            "mse": float(metrics["mse"]),
        }
    except Exception as exc:
        return {"image_metric_error": str(exc)[:500]}


def _read_output_image_bytes(base_url: str, *, api_key: str, output_path: str) -> bytes:
    if output_path.startswith("artifact:"):
        query = urllib.parse.urlencode({"path": output_path, "api_key": api_key})
        status, body, error = _request_bytes(f"{base_url}/api/artifacts/file?{query}")
        if status != 200:
            raise RuntimeError(error or f"artifact download failed with HTTP {status}")
        return body
    path = Path(output_path)
    if path.exists():
        return path.read_bytes()
    raise FileNotFoundError(f"VTON output does not exist or is not an artifact ref: {output_path}")


def _rgb_image_from_bytes(data: bytes) -> RgbImage:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for SSIM/PSNR benchmark metrics") from exc
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert("RGB")
        return RgbImage(width=rgb.width, height=rgb.height, pixels=rgb.tobytes())


def _capture_system_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {"timestamp_ms": _now_ms()}
    try:
        import psutil

        memory = psutil.virtual_memory()
        snapshot.update(
            {
                "cpu_percent": float(psutil.cpu_percent(interval=None)),
                "memory_total_gb": round(float(memory.total) / 1e9, 6),
                "memory_used_gb": round(float(memory.used) / 1e9, 6),
                "memory_percent": float(memory.percent),
            }
        )
    except Exception as exc:
        snapshot["system_error"] = str(exc)[:200]

    gpus = _capture_gpu_snapshots()
    if gpus:
        snapshot["gpus"] = gpus
    return snapshot


def _capture_gpu_snapshots() -> list[dict[str, Any]]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    gpus: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 7:
            continue
        used_mb = _float(parts[3])
        total_mb = _float(parts[4])
        memory_percent = None
        if used_mb is not None and total_mb and total_mb > 0:
            memory_percent = round((used_mb / total_mb) * 100.0, 6)
        gpus.append(
            {
                "index": parts[0],
                "name": parts[1],
                "util_percent": _float(parts[2]),
                "memory_used_gb": round(used_mb / 1024.0, 6) if used_mb is not None else None,
                "memory_total_gb": round(total_mb / 1024.0, 6) if total_mb is not None else None,
                "memory_percent": memory_percent,
                "power_w": _float(parts[5]),
                "temperature_c": _float(parts[6]),
            }
        )
    return gpus


def _system_metrics_from_samples(samples: list[dict[str, Any]]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    cpu_values = [_float(sample.get("cpu_percent")) for sample in samples]
    memory_used_values = [_float(sample.get("memory_used_gb")) for sample in samples]
    memory_percent_values = [_float(sample.get("memory_percent")) for sample in samples]
    gpu_util_values: list[float] = []
    gpu_memory_values: list[float] = []
    gpu_memory_percent_values: list[float] = []
    gpu_power_values: list[float] = []
    gpu_temperature_values: list[float] = []
    gpu_count = 0
    for sample in samples:
        gpus = sample.get("gpus")
        if not isinstance(gpus, list):
            continue
        gpu_count = max(gpu_count, len(gpus))
        for gpu in gpus:
            if not isinstance(gpu, dict):
                continue
            _append_float(gpu_util_values, gpu.get("util_percent"))
            _append_float(gpu_memory_values, gpu.get("memory_used_gb"))
            _append_float(gpu_memory_percent_values, gpu.get("memory_percent"))
            _append_float(gpu_power_values, gpu.get("power_w"))
            _append_float(gpu_temperature_values, gpu.get("temperature_c"))

    _set_avg(metrics, "system_cpu_percent_avg", cpu_values)
    _set_max(metrics, "system_memory_used_gb_max", memory_used_values)
    _set_max(metrics, "system_memory_percent_max", memory_percent_values)
    _set_max(metrics, "system_gpu_util_percent_max", gpu_util_values)
    _set_max(metrics, "system_gpu_memory_used_gb_max", gpu_memory_values)
    _set_max(metrics, "system_gpu_memory_percent_max", gpu_memory_percent_values)
    _set_max(metrics, "system_gpu_power_w_max", gpu_power_values)
    _set_max(metrics, "system_gpu_temperature_c_max", gpu_temperature_values)
    if gpu_count:
        metrics["system_gpu_count"] = float(gpu_count)
    return metrics


def _poll_vton_job(base_url: str, *, api_key: str, job_id: str, timeout_s: float) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    system_samples: list[dict[str, Any]] = []
    last: dict[str, Any] = {"status": 0, "body": {}, "error": "polling did not start", "system_samples": system_samples}
    while time.time() < deadline:
        system_samples.append(_capture_system_snapshot())
        query = urllib.parse.urlencode({"api_key": api_key})
        status, body, error = _request_json("GET", f"{base_url}/api/vton/jobs/{urllib.parse.quote(job_id)}?{query}")
        last = {"status": status, "body": body, "error": error, "system_samples": system_samples}
        if body.get("status") in {"completed", "failed"}:
            return last
        time.sleep(2)
    last["error"] = f"VTON job polling timed out after {timeout_s:.0f}s"
    return last


def _failed_vton_record(*, index: int, message: str) -> dict[str, Any]:
    now = _now_ms()
    return {
        "workload": "vton",
        "scenario": "vton_job_real",
        "target": "champion",
        "index": index,
        "ok": False,
        "status": "failed",
        "http_status": 0,
        "latency_ms": 0,
        "started_epoch_ms": now,
        "ended_epoch_ms": now,
        "request_id": "",
        "error_code": "vton_upload_failed",
        "error_message": message,
        "metrics": {},
    }


def _log_summary_to_mlflow(
    client: MlflowRestClient,
    *,
    experiment_id: str,
    experiment_name: str,
    summary: list[dict[str, Any]],
    paths: dict[str, str],
    config: dict[str, Any],
) -> list[dict[str, str]]:
    run_refs: list[dict[str, str]] = []
    for row in summary:
        workload = str(row.get("workload") or "unknown")
        scenario = str(row.get("scenario") or "unknown")
        run_id = client.start_run(
            experiment_id=experiment_id,
            run_name=f"{scenario}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
            tags={
                "tryops.schema": SCHEMA_VERSION,
                "tryops.benchmark.experiment": experiment_name,
                "tryops.benchmark.workload": workload,
                "tryops.benchmark.scenario": scenario,
            },
        )
        metrics = {
            key: float(value)
            for key, value in row.items()
            if isinstance(value, int | float) and key not in {"requests", "success_count", "error_count"}
        }
        metrics["requests"] = float(row.get("requests") or 0)
        metrics["success_count"] = float(row.get("success_count") or 0)
        metrics["error_count"] = float(row.get("error_count") or 0)
        params = {
            "workload": workload,
            "scenario": scenario,
            "target": str(row.get("target") or ""),
            "base_url": str(config.get("base_url") or ""),
            "json_report": paths["json"],
            "summary_csv": paths["summary_csv"],
            "markdown_report": paths["markdown"],
        }
        client.log_batch(run_id=run_id, metrics=metrics, params=params)
        run_refs.append({"run_id": run_id, "workload": workload, "scenario": scenario})
    return run_refs


def _log_artifacts_to_mlflow(
    client: MlflowRestClient,
    *,
    run_refs: list[dict[str, str]],
    records: list[dict[str, Any]],
    paths: dict[str, str],
    base_url: str,
    api_key: str,
) -> list[dict[str, Any]]:
    uploader = _S3ArtifactUploader.from_environment()
    results: list[dict[str, Any]] = []
    common_files = {
        "reports/benchmark.json": Path(paths["json"]),
        "reports/benchmark_summary.csv": Path(paths["summary_csv"]),
        "reports/benchmark_records.csv": Path(paths["records_csv"]),
        "reports/vton_benchmark_report.md": Path(paths["markdown"]),
    }
    for run_ref in run_refs:
        run_id = str(run_ref["run_id"])
        workload = str(run_ref.get("workload") or "")
        scenario = str(run_ref.get("scenario") or "")
        run_result: dict[str, Any] = {"run_id": run_id, "uploaded": [], "errors": []}
        try:
            run_info = client.get_run(run_id).get("run", {}).get("info", {})
            artifact_uri = str(run_info.get("artifact_uri") or "")
            scenario_records = [
                record
                for record in records
                if str(record.get("workload") or "") == workload and str(record.get("scenario") or "") == scenario
            ]
            for artifact_path, local_path in common_files.items():
                _upload_file_artifact(uploader, artifact_uri, artifact_path, local_path, run_result)
            _upload_bytes_artifact(
                uploader,
                artifact_uri,
                f"records/{scenario}_records.json",
                json.dumps(scenario_records, indent=2, sort_keys=True).encode("utf-8"),
                "application/json",
                run_result,
            )
            _upload_record_images(
                uploader,
                artifact_uri,
                records=scenario_records,
                base_url=base_url,
                api_key=api_key,
                run_result=run_result,
            )
        except Exception as exc:
            run_result["errors"].append(str(exc)[:500])
        client.log_batch(
            run_id=run_id,
            metrics={
                "mlflow_artifact_count": float(len(run_result["uploaded"])),
                "mlflow_artifact_error_count": float(len(run_result["errors"])),
            },
            params={},
            tags={"tryops.benchmark.artifacts": "minio_s3"},
        )
        results.append(run_result)
    return results


def _upload_record_images(
    uploader: "_S3ArtifactUploader",
    artifact_uri: str,
    *,
    records: list[dict[str, Any]],
    base_url: str,
    api_key: str,
    run_result: dict[str, Any],
) -> None:
    for record in records:
        if str(record.get("scenario") or "") != "vton_job_real":
            continue
        request_id = str(record.get("request_id") or f"record-{record.get('index', 0)}")
        person_path = Path(str(record.get("ground_truth_path") or ""))
        garment_path = Path(str(record.get("garment_path") or ""))
        if person_path.exists():
            _upload_file_artifact(
                uploader,
                artifact_uri,
                f"images/{request_id}/ground_truth_person{person_path.suffix.lower() or '.jpg'}",
                person_path,
                run_result,
            )
        if garment_path.exists():
            _upload_file_artifact(
                uploader,
                artifact_uri,
                f"images/{request_id}/garment{garment_path.suffix.lower() or '.jpg'}",
                garment_path,
                run_result,
            )
        output_path = str(record.get("output_path") or "")
        if output_path:
            try:
                output_bytes = _read_output_image_bytes(base_url, api_key=api_key, output_path=output_path)
                _upload_bytes_artifact(
                    uploader,
                    artifact_uri,
                    f"images/{request_id}/output.png",
                    output_bytes,
                    "image/png",
                    run_result,
                )
            except Exception as exc:
                run_result["errors"].append(f"output image upload failed: {str(exc)[:300]}")
        system_samples = record.get("system_samples")
        if isinstance(system_samples, list):
            _upload_bytes_artifact(
                uploader,
                artifact_uri,
                f"system/{request_id}_system_samples.json",
                json.dumps(system_samples, indent=2, sort_keys=True).encode("utf-8"),
                "application/json",
                run_result,
            )


def _upload_file_artifact(
    uploader: "_S3ArtifactUploader",
    artifact_uri: str,
    artifact_path: str,
    local_path: Path,
    run_result: dict[str, Any],
) -> None:
    try:
        content_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
        _upload_bytes_artifact(uploader, artifact_uri, artifact_path, local_path.read_bytes(), content_type, run_result)
    except Exception as exc:
        run_result["errors"].append(f"{artifact_path}: {str(exc)[:300]}")


def _upload_bytes_artifact(
    uploader: "_S3ArtifactUploader",
    artifact_uri: str,
    artifact_path: str,
    data: bytes,
    content_type: str,
    run_result: dict[str, Any],
) -> None:
    uploader.upload(artifact_uri=artifact_uri, artifact_path=artifact_path, data=data, content_type=content_type)
    run_result["uploaded"].append(artifact_path)


class _S3ArtifactUploader:
    def __init__(self, *, endpoints: list[str], access_key: str, secret_key: str, region: str = "us-east-1") -> None:
        self.endpoints = endpoints
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region

    @classmethod
    def from_environment(cls) -> "_S3ArtifactUploader":
        endpoints = _minio_endpoints()
        access_key = _docker_secret("tryops_minio_root_user") or _config_value("TRYOPS_MINIO_ROOT_USER")
        secret_key = _docker_secret("tryops_minio_root_password") or _config_value("TRYOPS_MINIO_ROOT_PASSWORD")
        if not access_key or not secret_key:
            access_key = access_key or _config_value("AWS_ACCESS_KEY_ID")
            secret_key = secret_key or _config_value("AWS_SECRET_ACCESS_KEY")
        if not access_key or not secret_key:
            raise RuntimeError("missing MinIO credentials for MLflow artifact upload")
        return cls(endpoints=endpoints, access_key=access_key, secret_key=secret_key)

    def upload(self, *, artifact_uri: str, artifact_path: str, data: bytes, content_type: str) -> None:
        bucket, prefix = _parse_s3_uri(artifact_uri)
        key = "/".join(part.strip("/") for part in [prefix, artifact_path] if part.strip("/"))
        last_error = ""
        for endpoint in self.endpoints:
            try:
                self._put(endpoint=endpoint, bucket=bucket, key=key, data=data, content_type=content_type)
                return
            except Exception as exc:
                last_error = str(exc)
        raise RuntimeError(last_error or "all MinIO artifact upload endpoints failed")

    def _put(self, *, endpoint: str, bucket: str, key: str, data: bytes, content_type: str) -> None:
        parsed_endpoint = urllib.parse.urlparse(endpoint)
        host = parsed_endpoint.netloc
        canonical_uri = "/" + bucket + "/" + "/".join(urllib.parse.quote(part, safe="") for part in key.split("/"))
        url = endpoint.rstrip("/") + canonical_uri
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(data).hexdigest()
        headers = {
            "content-type": content_type,
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        signed_headers = ";".join(sorted(headers))
        canonical_headers = "".join(f"{key}:{headers[key]}\n" for key in sorted(headers))
        canonical_request = "\n".join(["PUT", canonical_uri, "", canonical_headers, signed_headers, payload_hash])
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signing_key = _aws_v4_signing_key(self.secret_key, date_stamp, self.region, "s3")
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        request = urllib.request.Request(
            url,
            data=data,
            headers={**headers, "Authorization": authorization},
            method="PUT",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()


def _minio_endpoints() -> list[str]:
    endpoints: list[str] = []
    for value in [
        _config_value("TRYOPS_STACK_MINIO_URL"),
        _config_value("MLFLOW_S3_ENDPOINT_URL"),
        _endpoint_from_port(_config_value("TRYOPS_MINIO_PORT")),
        "http://127.0.0.1:19000",
        "http://127.0.0.1:9000",
    ]:
        normalized = _normalize_endpoint(value)
        if normalized and normalized not in endpoints:
            endpoints.append(normalized)
    return endpoints


def _endpoint_from_port(port: str) -> str:
    return f"http://127.0.0.1:{port}" if port else ""


def _normalize_endpoint(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        return ""
    if "://" not in value:
        value = "http://" + value
    parsed = urllib.parse.urlparse(value)
    if parsed.hostname in {"minio", "localhost"}:
        port = parsed.port or 9000
        return f"{parsed.scheme}://127.0.0.1:{port}"
    return value


def _docker_secret(name: str) -> str:
    try:
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "minio", "cat", f"/run/secrets/{name}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _config_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return _strip_quotes(value)
    env_path = ROOT / ".env"
    if not env_path.exists():
        return ""
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            if key.strip() == name:
                return _strip_quotes(raw_value.strip())
    except OSError:
        return ""
    return ""


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise RuntimeError(f"unsupported MLflow artifact URI: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def _aws_v4_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    key = ("AWS4" + secret_key).encode("utf-8")
    for value in [date_stamp, region, service, "aws4_request"]:
        key = hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()
    return key


def _append_float(values: list[float], value: Any) -> None:
    parsed = _float(value)
    if parsed is not None:
        values.append(parsed)


def _clean_float_values(values: list[float | None]) -> list[float]:
    return [value for value in values if value is not None]


def _set_avg(metrics: dict[str, float], key: str, values: list[float | None]) -> None:
    cleaned = _clean_float_values(values)
    if cleaned:
        metrics[key] = round(sum(cleaned) / len(cleaned), 6)


def _set_max(metrics: dict[str, float], key: str, values: list[float | None]) -> None:
    cleaned = _clean_float_values(values)
    if cleaned:
        metrics[key] = round(max(cleaned), 6)


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 300.0,
) -> tuple[int, dict[str, Any], str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"} if payload is not None else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return int(response.status), _parse_json_object(body), ""
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), _parse_json_object(body), body[:500]
    except OSError as exc:
        return 0, {}, str(exc)


def _request_bytes(url: str, *, timeout: float = 300.0) -> tuple[int, bytes, str]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as response:
            return int(response.status), response.read(), ""
    except urllib.error.HTTPError as exc:
        return int(exc.code), b"", exc.read().decode("utf-8", errors="replace")[:500]
    except OSError as exc:
        return 0, b"", str(exc)


def _parse_json_object(body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _error_code(body: dict[str, Any], fallback: str) -> str:
    nested = body.get("error") if isinstance(body.get("error"), dict) else {}
    return str(body.get("code") or nested.get("code") or fallback)


def _error_message(body: dict[str, Any], fallback: str) -> str:
    nested = body.get("error") if isinstance(body.get("error"), dict) else {}
    return str(body.get("message") or nested.get("message") or fallback or "")[:500]


def _print_summary_table(rows: list[dict[str, Any]]) -> None:
    print()
    print("workload  scenario             requests  success%  ssim      psnr      avg_ms    p95_ms    rps")
    for row in rows:
        print(
            f"{str(row.get('workload', '-'))[:8]:8}  "
            f"{str(row.get('scenario', '-'))[:20]:20}  "
            f"{int(row.get('requests') or 0):8d}  "
            f"{float(row.get('success_rate_percent') or 0):8.2f}  "
            f"{_display_float(row.get('avg_ssim')):>8}  "
            f"{_display_float(row.get('avg_psnr')):>8}  "
            f"{float(row.get('avg_latency_ms') or 0):8.2f}  "
            f"{float(row.get('p95_latency_ms') or 0):8.2f}  "
            f"{float(row.get('throughput_rps') or 0):8.3f}"
        )


def _nested_text(data: dict[str, Any], path: list[str]) -> str:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return "" if value is None else str(value)


def _optional_path_env(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    return Path(raw) if raw else None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_float(value: Any) -> str:
    parsed = _float(value)
    return "-" if parsed is None else f"{parsed:.4f}"


def _now_ms() -> int:
    return int(time.time() * 1000)


if __name__ == "__main__":
    raise SystemExit(main())
