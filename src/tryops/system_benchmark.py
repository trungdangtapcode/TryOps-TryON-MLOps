from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any


SCHEMA_VERSION = "tryops.vton_benchmark.v1"

SUMMARY_COLUMNS = [
    "workload",
    "scenario",
    "target",
    "requests",
    "success_rate_percent",
    "avg_latency_ms",
    "p95_latency_ms",
    "throughput_rps",
    "error_rate_percent",
    "avg_ssim",
    "avg_psnr",
    "avg_model_latency_ms",
    "avg_system_cpu_percent",
    "max_system_memory_used_gb",
    "max_system_memory_percent",
    "max_system_gpu_util_percent",
    "max_system_gpu_memory_used_gb",
    "max_system_gpu_memory_percent",
    "max_system_gpu_power_w",
    "max_system_gpu_temperature_c",
    "avg_tokens_per_second",
    "avg_cost_usd",
    "avg_quality_score",
    "max_gpu_memory_gb",
]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def build_system_benchmark_report(
    *,
    records: list[dict[str, Any]],
    mlflow: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    summaries = summarize_records(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "config": config,
        "mlflow": mlflow,
        "records": records,
        "summary": summaries,
        "notes": [
            "Benchmarks drive live TryOps VTON upload and job APIs against image pairs from data/.",
            "MLflow receives one run per VTON scenario so the Tracking UI can plot latency, throughput, quality, and success metrics.",
        ],
    }


def discover_vton_dataset_pairs(data_dir: str | Path, *, limit: int) -> list[dict[str, str]]:
    """Return person/garment pairs from the VITON-style ``data/`` directory."""

    root = Path(data_dir)
    person_dir = root / "test_img"
    garment_dir = root / "test_color"
    if limit < 1:
        return []
    if not person_dir.is_dir() or not garment_dir.is_dir():
        raise FileNotFoundError(f"expected VTON dataset folders under {root}: test_img/ and test_color/")

    garments_by_id = {_pair_id(path): path for path in _image_files(garment_dir)}
    pairs: list[dict[str, str]] = []
    for person in _image_files(person_dir):
        pair_id = _pair_id(person)
        garment = garments_by_id.get(pair_id)
        if garment is None:
            continue
        pairs.append(
            {
                "pair_id": pair_id,
                "person_image": str(person),
                "garment_image": str(garment),
            }
        )
        if len(pairs) >= limit:
            break
    if not pairs:
        raise FileNotFoundError(f"no matched VTON image pairs found in {person_dir} and {garment_dir}")
    return pairs


def summarize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(str(record.get("workload", "unknown")), str(record.get("scenario", "unknown")))].append(record)

    rows: list[dict[str, Any]] = []
    for (workload, scenario), group in sorted(grouped.items()):
        total = len(group)
        ok = [record for record in group if bool(record.get("ok"))]
        errors = total - len(ok)
        latencies = [_float(record.get("latency_ms")) for record in group if _float(record.get("latency_ms")) is not None]
        duration_s = _duration_s(group, latencies)
        metrics = [record.get("metrics", {}) for record in group if isinstance(record.get("metrics"), dict)]
        rows.append(
            {
                "workload": workload,
                "scenario": scenario,
                "target": _first_text(group, "target"),
                "requests": total,
                "success_count": len(ok),
                "error_count": errors,
                "success_rate_percent": _metric(100.0 * len(ok) / total if total else 0.0),
                "error_rate_percent": _metric(100.0 * errors / total if total else 0.0),
                "avg_latency_ms": _metric(mean(latencies)) if latencies else None,
                "p95_latency_ms": _metric(_percentile(latencies, 0.95)) if latencies else None,
                "throughput_rps": _metric(total / duration_s) if duration_s > 0 else None,
                "avg_ssim": _metric(_mean_metric(metrics, "ssim")),
                "avg_psnr": _metric(_mean_metric(metrics, "psnr")),
                "avg_model_latency_ms": _metric(_mean_metric(metrics, "model_latency_ms")),
                "avg_system_cpu_percent": _metric(_mean_metric(metrics, "system_cpu_percent_avg")),
                "max_system_memory_used_gb": _metric(_max_metric(metrics, "system_memory_used_gb_max")),
                "max_system_memory_percent": _metric(_max_metric(metrics, "system_memory_percent_max")),
                "max_system_gpu_util_percent": _metric(_max_metric(metrics, "system_gpu_util_percent_max")),
                "max_system_gpu_memory_used_gb": _metric(_max_metric(metrics, "system_gpu_memory_used_gb_max")),
                "max_system_gpu_memory_percent": _metric(_max_metric(metrics, "system_gpu_memory_percent_max")),
                "max_system_gpu_power_w": _metric(_max_metric(metrics, "system_gpu_power_w_max")),
                "max_system_gpu_temperature_c": _metric(_max_metric(metrics, "system_gpu_temperature_c_max")),
                "avg_tokens_per_second": _metric(_mean_metric(metrics, "tokens_per_second")),
                "avg_output_tokens": _metric(_mean_metric(metrics, "output_tokens")),
                "avg_cost_usd": _metric(_mean_metric(metrics, "cost_usd")),
                "avg_quality_score": _metric(_mean_metric(metrics, "quality_score")),
                "max_gpu_memory_gb": _metric(_max_metric(metrics, "gpu_memory_gb")),
            }
        )
    return rows


def write_benchmark_artifacts(
    *,
    report: dict[str, Any],
    output_dir: str | Path,
    report_path: str | Path,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report_file = output / "benchmark.json"
    summary_csv = output / "benchmark_summary.csv"
    records_csv = output / "benchmark_records.csv"
    markdown_file = Path(report_path)
    markdown_file.parent.mkdir(parents=True, exist_ok=True)

    report_file.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_summary_csv(report.get("summary", []), summary_csv)
    write_records_csv(report.get("records", []), records_csv)
    markdown_file.write_text(render_markdown_report(report), encoding="utf-8")
    return {
        "json": str(report_file),
        "summary_csv": str(summary_csv),
        "records_csv": str(records_csv),
        "markdown": str(markdown_file),
    }


def write_summary_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_records_csv(records: list[dict[str, Any]], path: str | Path) -> None:
    fieldnames = [
        "workload",
        "scenario",
        "target",
        "index",
        "ok",
        "status",
        "http_status",
        "latency_ms",
        "request_id",
        "error_code",
        "error_message",
        "ground_truth_path",
        "output_path",
        "ssim",
        "psnr",
        "system_cpu_percent_avg",
        "system_memory_used_gb_max",
        "system_memory_percent_max",
        "system_gpu_util_percent_max",
        "system_gpu_memory_used_gb_max",
        "system_gpu_memory_percent_max",
        "system_gpu_power_w_max",
        "system_gpu_temperature_c_max",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            metrics = record.get("metrics", {}) if isinstance(record.get("metrics"), dict) else {}
            row["ssim"] = metrics.get("ssim")
            row["psnr"] = metrics.get("psnr")
            row["system_cpu_percent_avg"] = metrics.get("system_cpu_percent_avg")
            row["system_memory_used_gb_max"] = metrics.get("system_memory_used_gb_max")
            row["system_memory_percent_max"] = metrics.get("system_memory_percent_max")
            row["system_gpu_util_percent_max"] = metrics.get("system_gpu_util_percent_max")
            row["system_gpu_memory_used_gb_max"] = metrics.get("system_gpu_memory_used_gb_max")
            row["system_gpu_memory_percent_max"] = metrics.get("system_gpu_memory_percent_max")
            row["system_gpu_power_w_max"] = metrics.get("system_gpu_power_w_max")
            row["system_gpu_temperature_c_max"] = metrics.get("system_gpu_temperature_c_max")
            writer.writerow(row)


def render_markdown_report(report: dict[str, Any]) -> str:
    mlflow = report.get("mlflow", {}) if isinstance(report.get("mlflow"), dict) else {}
    config = report.get("config", {}) if isinstance(report.get("config"), dict) else {}
    rows = report.get("summary", []) if isinstance(report.get("summary"), list) else []
    lines = [
        "# Benchmark VTON TryOps - ket qua tu MLflow",
        "",
        "Toan bo ket qua benchmark VTON duoc ghi nhan va theo doi qua MLflow. "
        "Moi scenario ghi thanh mot run rieng de co the ve chart theo latency, throughput, success rate, quality va GPU metrics.",
        "",
        f"- MLflow experiment: `{mlflow.get('experiment_name', '-')}`",
        f"- MLflow URL: {mlflow.get('experiment_url', '-')}",
        f"- Gateway/API: `{config.get('base_url', '-')}`",
        f"- Created at: `{report.get('created_at', '-')}`",
        "",
        "| Workload | Scenario | Dataset/Target | Samples | Success (%) ↑ | SSIM ↑ | PSNR ↑ | Avg latency (ms) ↓ | P95 latency (ms) ↓ | Throughput (req/s) ↑ | Error (%) ↓ | Model latency (ms) ↓ | GPU util (%) ↑ | GPU VRAM (GB) ↓ | Host RAM (GB) ↓ |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {workload} | {scenario} | {target} | {requests} | {success} | {ssim} | {psnr} | {avg} | {p95} | "
            "{rps} | {error} | {model_latency} | {gpu_util} | {gpu} | {ram} |".format(
                workload=_cell(row.get("workload")),
                scenario=_cell(row.get("scenario")),
                target=_cell(row.get("target")),
                requests=_cell(row.get("requests")),
                success=_cell(row.get("success_rate_percent")),
                ssim=_cell(row.get("avg_ssim")),
                psnr=_cell(row.get("avg_psnr")),
                avg=_cell(row.get("avg_latency_ms")),
                p95=_cell(row.get("p95_latency_ms")),
                rps=_cell(row.get("throughput_rps")),
                error=_cell(row.get("error_rate_percent")),
                model_latency=_cell(row.get("avg_model_latency_ms")),
                gpu_util=_cell(row.get("max_system_gpu_util_percent")),
                gpu=_cell(row.get("max_system_gpu_memory_used_gb") or row.get("max_gpu_memory_gb")),
                ram=_cell(row.get("max_system_memory_used_gb")),
            )
        )
    lines.extend(
        [
            "",
            "_Bang 5.1. Ket qua benchmark VTON TryOps tren data/ - tracked qua MLflow._",
            "",
            "Ghi chu: SSIM va PSNR duoc tinh giua VTON output va anh ground truth tu data/test_img cung pair_id. Latency la wall-clock latency cua upload/job; model latency la metric rieng tu VTON report.",
            "",
        ]
    )
    return "\n".join(lines)


def _duration_s(group: list[dict[str, Any]], latencies_ms: list[float]) -> float:
    starts = [_float(record.get("started_epoch_ms")) for record in group]
    ends = [_float(record.get("ended_epoch_ms")) for record in group]
    starts = [value for value in starts if value is not None]
    ends = [value for value in ends if value is not None]
    if starts and ends:
        return max((max(ends) - min(starts)) / 1000.0, 0.001)
    return max(sum(latencies_ms) / 1000.0, 0.001) if latencies_ms else 0.0


def _image_files(path: Path) -> list[Path]:
    return sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES)


def _pair_id(path: Path) -> str:
    stem = path.stem
    if "_" in stem:
        return stem.rsplit("_", 1)[0]
    return stem


def _mean_metric(metrics: list[dict[str, Any]], key: str) -> float | None:
    values = [_float(item.get(key)) for item in metrics]
    values = [value for value in values if value is not None]
    return mean(values) if values else None


def _max_metric(metrics: list[dict[str, Any]], key: str) -> float | None:
    values = [_float(item.get(key)) for item in metrics]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return float(ordered[index])


def _first_text(group: list[dict[str, Any]], key: str) -> str:
    for record in group:
        value = str(record.get(key, "")).strip()
        if value:
            return value
    return "-"


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        if abs(value) >= 100:
            return f"{value:,.2f}"
        if abs(value) >= 1:
            return f"{value:,.3f}"
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")
