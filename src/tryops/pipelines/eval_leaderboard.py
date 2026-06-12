"""Eval leaderboard (Theme N) — statistically honest variant ranking.

Consumes one or more ``tryops.llm_benchmark.v1`` artifacts (per-record, for
bootstrap CIs and judge/rubric agreement) and, when present, the real
``pareto.json`` and ``energy_sweep.json`` artifacts (for throughput, VRAM, SLO,
and energy per variant). Produces ``tryops.eval_leaderboard.v1``: each variant
ranked with a quality confidence interval, judge-vs-rubric Cohen's kappa, and the
optimization/sustainability metrics — the single board the recommendation engine
and control-room UI consume. Runs fully offline (judge degrades to the rubric).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tryops.evaluation import (
    cohens_kappa,
    concept_coverage_score,
    paired_significance,
)
from tryops.llm_judge import judge_available, score_answer
from tryops.native_eval_stats import bootstrap_ci_preferred as bootstrap_ci

_PASS_THRESHOLD = 0.6


def _score_benchmark(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    variant = data.get("adapter", path.stem)
    rubric_scores: list[float] = []
    judge_scores: list[float] = []
    rubric_labels: list[str] = []
    judge_labels: list[str] = []
    prompt_ids: list[str] = []
    for rec in data.get("records", []):
        expected = list(rec.get("expected_characteristics", []))
        answer = rec.get("output_text", "")
        rubric = concept_coverage_score(answer, expected)["score"]
        judge = score_answer(rec.get("prompt", ""), answer, expected)["score"]
        rubric_scores.append(rubric)
        judge_scores.append(judge)
        rubric_labels.append("pass" if rubric >= _PASS_THRESHOLD else "fail")
        judge_labels.append("pass" if judge >= _PASS_THRESHOLD else "fail")
        prompt_ids.append(str(rec.get("id", "")))
    row: dict[str, Any] = {
        "variant": variant,
        "source_artifact": str(path),
        "n": len(judge_scores),
        "judge_scores": judge_scores,
        "prompt_ids": prompt_ids,
    }
    if judge_scores:
        row["quality_ci"] = bootstrap_ci(judge_scores)
        row["rubric_ci"] = bootstrap_ci(rubric_scores)
        row["quality"] = row["quality_ci"]["point"]
        row["judge_rubric_kappa"] = cohens_kappa(judge_labels, rubric_labels)
    return row


def run_eval_leaderboard(
    *,
    benchmark_paths: list[str | Path],
    output_path: str | Path,
    pareto_path: str | Path | None = None,
    energy_path: str | Path | None = None,
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    for bp in benchmark_paths:
        p = Path(bp)
        if not p.exists():
            continue
        row = _score_benchmark(p)
        rows[row["variant"]] = row

    # Enrich with real optimization metrics from the Pareto artifact.
    if pareto_path and Path(pareto_path).exists():
        pareto = json.loads(Path(pareto_path).read_text(encoding="utf-8"))
        for v in pareto.get("variants", []):
            if not v.get("available"):
                continue
            row = rows.setdefault(v["variant"], {"variant": v["variant"], "n": 0})
            row["tokens_per_second"] = v.get("tokens_per_second")
            row["peak_vram_gb"] = v.get("peak_vram_gb")
            row["latency_p50_ms"] = v.get("latency_p50_ms")
            row["slo_verdict"] = v.get("slo", {}).get("verdict")
            row.setdefault("quality", v.get("quality_score"))

    # Enrich with sustainability metrics from the energy sweep.
    if energy_path and Path(energy_path).exists():
        energy = json.loads(Path(energy_path).read_text(encoding="utf-8"))
        for v in energy.get("variants", []):
            if not v.get("available"):
                continue
            row = rows.setdefault(v["variant"], {"variant": v["variant"], "n": 0})
            row["energy_wh_per_1k_tokens"] = v.get("energy_wh_per_1k_tokens")
            row["sci_g_per_1k_tokens"] = v.get("sci_g_per_1k_tokens")

    ranked = sorted(
        rows.values(),
        key=lambda r: (r.get("quality") if r.get("quality") is not None else -1.0,
                       r.get("tokens_per_second") or 0.0),
        reverse=True,
    )

    # Paired significance between the top two variants when they share per-prompt
    # judge scores over the same prompts (statistically honest "is A really better").
    significance = None
    scored = [r for r in ranked if r.get("judge_scores")]
    if len(scored) >= 2:
        a, b = scored[0], scored[1]
        if a["prompt_ids"] == b["prompt_ids"] and a["prompt_ids"]:
            significance = {
                "variant_a": a["variant"],
                "variant_b": b["variant"],
                **paired_significance(a["judge_scores"], b["judge_scores"]),
            }

    # Drop bulky per-prompt arrays from the persisted board (keep the stats).
    for r in ranked:
        r.pop("judge_scores", None)
        r.pop("prompt_ids", None)

    report = {
        "schema_version": "tryops.eval_leaderboard.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "judge_backend": "claude" if judge_available() else "offline-rubric",
        "ranking": [r["variant"] for r in ranked],
        "leaderboard": ranked,
        "top_two_significance": significance,
        "notes": [
            "Quality is a judge score with a percentile bootstrap CI; pass threshold "
            f"{_PASS_THRESHOLD} for judge-vs-rubric kappa.",
            "Model-agnostic concept-coverage rubric replaces exact-phrase matching; "
            "Claude judge used when ANTHROPIC_API_KEY is set, else the rubric.",
        ],
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
