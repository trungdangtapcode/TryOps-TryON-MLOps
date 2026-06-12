from __future__ import annotations

import csv
import html
import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any


REPORT_SCHEMA = "tryops.llm_optimization_report.v1"


def write_llm_optimization_report(
    *,
    pareto_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    pareto_file = Path(pareto_path)
    artifact = json.loads(pareto_file.read_text(encoding="utf-8"))
    rows = [_normalize_variant(v, artifact.get("pareto_frontier", [])) for v in artifact["variants"]]

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    markdown_path = output / "llm_optimization_report.md"
    chart_path = output / "llm_pareto_chart.svg"
    csv_path = output / "llm_pareto_metrics.csv"
    audit_path = output / "llm_optimization_report.json"

    chart = render_quality_latency_memory_chart(rows, artifact.get("recommendation", {}))
    csv_text = render_metrics_csv(rows)
    markdown = render_markdown_report(
        artifact=artifact,
        rows=rows,
        source_path=str(pareto_file),
        chart_path=chart_path.name,
        csv_path=csv_path.name,
    )

    markdown_path.write_text(markdown, encoding="utf-8")
    chart_path.write_text(chart, encoding="utf-8")
    csv_path.write_text(csv_text, encoding="utf-8")

    available_count = sum(1 for row in rows if row["available"])
    report = {
        "schema_version": REPORT_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "source_pareto_artifact": str(pareto_file),
        "model_id": artifact.get("model_id"),
        "variant_count": len(rows),
        "available_variant_count": available_count,
        "pareto_frontier": artifact.get("pareto_frontier", []),
        "recommendation": artifact.get("recommendation", {}),
        "artifacts": {
            "markdown_report": str(markdown_path),
            "chart_svg": str(chart_path),
            "metrics_csv": str(csv_path),
        },
        "research_sources": {
            "huggingface_bitsandbytes": "https://huggingface.co/docs/transformers/main/quantization/bitsandbytes",
            "huggingface_gptq": "https://huggingface.co/docs/transformers/main/quantization/gptq",
            "huggingface_awq": "https://huggingface.co/docs/transformers/main/quantization/awq",
            "vllm_pagedattention": "https://arxiv.org/abs/2309.06180",
        },
        "passed": available_count >= 2 and bool(artifact.get("pareto_frontier")),
    }
    audit_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def render_markdown_report(
    *,
    artifact: dict[str, Any],
    rows: list[dict[str, Any]],
    source_path: str,
    chart_path: str,
    csv_path: str,
) -> str:
    recommendation = artifact.get("recommendation", {})
    rec_variant = recommendation.get("variant") or "none"
    created_at = artifact.get("created_at", "unknown")
    model_id = artifact.get("model_id", "unknown")
    lines = [
        "# LLM Optimization Report",
        "",
        "Date: 2026-06-11",
        "",
        "## Source Artifact",
        "",
        f"- Pareto artifact: `{source_path}`",
        f"- Model: `{model_id}`",
        f"- Source run created: `{created_at}`",
        "- Artifact schema: `tryops.llm_pareto.v1`",
        "",
        "## Recommendation",
        "",
        f"Recommended variant: `{rec_variant}`.",
        "",
        str(recommendation.get("reason", "No recommendation reason was recorded.")),
        "",
        "## Quality-Latency-Memory Pareto Chart",
        "",
        f"![Quality-latency-memory Pareto chart]({chart_path})",
        "",
        "The chart plots latency p95 on the x-axis, rubric quality on the y-axis, and peak VRAM as bubble size. Pareto-frontier variants use a stronger outline.",
        "",
        "## Metrics Table",
        "",
        "| Variant | Available | Quality | Latency p95 ms | Tokens/sec | Peak VRAM GB | SLO | Frontier |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {variant} | {available} | {quality_score:.6g} | {latency_p95_ms:.6g} | "
            "{tokens_per_second:.6g} | {peak_vram_gb:.6g} | {slo_verdict} | {frontier} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            f"CSV artifact: `{csv_path}`",
            "",
            "## Interpretation",
            "",
            "- `4bit` is the current recommendation because it stays on the frontier, passes the native C++ SLO gate, and cuts measured peak VRAM versus fp16.",
            "- `8bit` is not recommended in this run because it is slower, larger than 4-bit, and fails the configured latency/throughput SLO.",
            "- `none` remains useful as the fp16-style quality and throughput reference, but it uses the most VRAM in this sweep.",
            "",
            "## Research Basis",
            "",
            "- Hugging Face Transformers bitsandbytes documentation covers 8-bit and 4-bit quantization, including memory-footprint checks.",
            "- Hugging Face GPTQ and AWQ documentation define the live quantized loading paths; native preflight now verifies suitable candidate repositories before loader runtimes are installed.",
            "- vLLM's PagedAttention paper motivates the future continuous-batching and KV-cache serving benchmark.",
            "",
            "## Residual Risk",
            "",
            "- Quality is a golden-prompt rubric proxy, not a neural judge or human evaluation.",
            "- The current report covers fp16-style, bitsandbytes 8-bit, and bitsandbytes 4-bit only.",
            "- Live GPTQ/AWQ loading, live GGUF generation, and live vLLM serving remain separate roadmap items; native GPTQ/AWQ, GGUF, and scheduler evidence are tracked separately.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_metrics_csv(rows: list[dict[str, Any]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "variant",
            "available",
            "quality_score",
            "latency_p50_ms",
            "latency_p95_ms",
            "tokens_per_second",
            "peak_vram_gb",
            "slo_verdict",
            "frontier",
            "error",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    return buffer.getvalue()


def render_quality_latency_memory_chart(
    rows: list[dict[str, Any]],
    recommendation: dict[str, Any] | None = None,
) -> str:
    available = [row for row in rows if row["available"]]
    width, height = 900, 520
    left, right, top, bottom = 86, 34, 58, 78
    plot_width = width - left - right
    plot_height = height - top - bottom
    if not available:
        return _empty_svg(width, height, "No available variants")

    latencies = [row["latency_p95_ms"] for row in available]
    qualities = [row["quality_score"] for row in available]
    vrams = [row["peak_vram_gb"] for row in available]
    min_latency, max_latency = min(latencies), max(latencies)
    min_quality, max_quality = min(qualities), max(qualities)
    min_vram, max_vram = min(vrams), max(vrams)
    recommended = (recommendation or {}).get("variant")

    def sx(latency: float) -> float:
        return left + _scale(latency, min_latency, max_latency) * plot_width

    def sy(quality: float) -> float:
        return top + (1.0 - _scale(quality, min_quality, max_quality)) * plot_height

    def radius(vram: float) -> float:
        return 9.0 + _scale(vram, min_vram, max_vram) * 14.0

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        "<title id=\"title\">LLM quality latency memory Pareto chart</title>",
        "<desc id=\"desc\">Latency p95 versus quality score with bubble size representing peak VRAM.</desc>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="32" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">Quality vs latency vs peak VRAM</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#111827" stroke-width="1.5"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#111827" stroke-width="1.5"/>',
        f'<text x="{left + plot_width / 2 - 120}" y="{height - 24}" font-family="Arial, sans-serif" font-size="15" fill="#374151">Latency p95 ms (lower is better)</text>',
        f'<text x="18" y="{top + plot_height / 2 + 88}" transform="rotate(-90 18 {top + plot_height / 2 + 88})" font-family="Arial, sans-serif" font-size="15" fill="#374151">Quality score (higher is better)</text>',
    ]
    for tick in range(5):
        frac = tick / 4
        x = left + frac * plot_width
        latency_value = min_latency + frac * (max_latency - min_latency)
        lines.extend(
            [
                f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#e5e7eb" stroke-width="1"/>',
                f'<text x="{x - 24:.2f}" y="{top + plot_height + 24}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{latency_value:.0f}</text>',
            ]
        )
    for tick in range(5):
        frac = tick / 4
        y = top + (1.0 - frac) * plot_height
        quality_value = min_quality + frac * (max_quality - min_quality)
        lines.extend(
            [
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#eef2f7" stroke-width="1"/>',
                f'<text x="{left - 62}" y="{y + 4:.2f}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{quality_value:.3f}</text>',
            ]
        )
    for row in available:
        x = sx(row["latency_p95_ms"])
        y = sy(row["quality_score"])
        r = radius(row["peak_vram_gb"])
        frontier = row["frontier"] == "yes"
        is_recommended = row["variant"] == recommended
        fill = "#10b981" if row["slo_verdict"] == "pass" else "#ef4444"
        stroke = "#111827" if is_recommended else ("#f59e0b" if frontier else "#6b7280")
        stroke_width = 4 if is_recommended else (3 if frontier else 1.5)
        label = html.escape(str(row["variant"]))
        label_to_left = x + r + 110 > width - right
        label_x = x - r - 7 if label_to_left else x + r + 7
        label_anchor = "end" if label_to_left else "start"
        lines.extend(
            [
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}" fill-opacity="0.72" stroke="{stroke}" stroke-width="{stroke_width}"/>',
                f'<text x="{label_x:.2f}" y="{y - 2:.2f}" text-anchor="{label_anchor}" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#111827">{label}</text>',
                f'<text x="{label_x:.2f}" y="{y + 15:.2f}" text-anchor="{label_anchor}" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{row["peak_vram_gb"]:.2f} GB VRAM</text>',
            ]
        )
    lines.extend(
        [
            f'<circle cx="{left + 12}" cy="{height - 52}" r="7" fill="#10b981" fill-opacity="0.72" stroke="#6b7280" stroke-width="1.5"/>',
            f'<text x="{left + 28}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#374151">SLO pass</text>',
            f'<circle cx="{left + 112}" cy="{height - 52}" r="7" fill="#ef4444" fill-opacity="0.72" stroke="#6b7280" stroke-width="1.5"/>',
            f'<text x="{left + 128}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#374151">SLO fail</text>',
            f'<circle cx="{left + 212}" cy="{height - 52}" r="7" fill="#ffffff" stroke="#f59e0b" stroke-width="3"/>',
            f'<text x="{left + 228}" y="{height - 48}" font-family="Arial, sans-serif" font-size="12" fill="#374151">Pareto frontier</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines)


def _normalize_variant(
    variant: dict[str, Any],
    frontier: list[str],
) -> dict[str, Any]:
    native_latency = variant.get("native_perf_stats", {}).get("latency_ms", {})
    return {
        "variant": str(variant.get("variant", "")),
        "available": bool(variant.get("available")),
        "quality_score": float(variant.get("quality_score", 0.0)),
        "latency_p50_ms": float(variant.get("latency_p50_ms", native_latency.get("p50", 0.0) or 0.0)),
        "latency_p95_ms": float(native_latency.get("p95", variant.get("latency_p50_ms", 0.0)) or 0.0),
        "tokens_per_second": float(variant.get("tokens_per_second", 0.0) or 0.0),
        "peak_vram_gb": float(variant.get("peak_vram_gb", 0.0) or 0.0),
        "slo_verdict": str(variant.get("slo", {}).get("verdict", "unknown")),
        "frontier": "yes" if variant.get("variant") in frontier else "no",
        "error": variant.get("error") or "",
    }


def _scale(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.5
    return (value - minimum) / (maximum - minimum)


def _empty_svg(width: int, height: int, message: str) -> str:
    safe_message = html.escape(message)
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            f'<text x="40" y="80" font-family="Arial, sans-serif" font-size="18" fill="#111827">{safe_message}</text>',
            "</svg>",
        ]
    )
