from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


NATIVE_EXPERIMENT_STATS_SCHEMA = "tryops.native_experiment_stats.v1"
DEFAULT_NATIVE_EXPERIMENT_STATS_CLI = Path("artifacts/native/tryops_experiment_stats_cli")


def analyze_with_native_experiment_stats(
    *,
    holdback: Mapping[str, Any],
    variants: Sequence[Mapping[str, Any]],
    experiment_id: str = "tryops-online-experiment",
    confidence: float = 0.95,
    alpha: float = 0.05,
    beta: float = 0.20,
    min_detectable_effect: float = 0.05,
    min_sample_size: float = 100.0,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    if not variants:
        raise ValueError("variants cannot be empty")
    cli = Path(
        str(
            cli_path
            or os.environ.get("TRYOPS_NATIVE_EXPERIMENT_STATS_CLI", DEFAULT_NATIVE_EXPERIMENT_STATS_CLI)
        )
    )
    if cli.exists() and os.access(cli, os.X_OK):
        completed = subprocess.run(
            [str(cli)],
            input=_wire_payload(
                holdback=holdback,
                variants=variants,
                experiment_id=experiment_id,
                confidence=confidence,
                alpha=alpha,
                beta=beta,
                min_detectable_effect=min_detectable_effect,
                min_sample_size=min_sample_size,
            ),
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            payload["available"] = payload.get("schema_version") == NATIVE_EXPERIMENT_STATS_SCHEMA
            payload["source"] = "native_cpp_cli"
            payload["returncode"] = completed.returncode
            payload["cli_path"] = str(cli)
            return payload
        return {
            "schema_version": NATIVE_EXPERIMENT_STATS_SCHEMA,
            "available": True,
            "source": "native_cpp_cli_error",
            "returncode": completed.returncode,
            "cli_path": str(cli),
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }

    fallback = _python_analyze(
        holdback=holdback,
        variants=variants,
        experiment_id=experiment_id,
        confidence=confidence,
        alpha=alpha,
        beta=beta,
        min_detectable_effect=min_detectable_effect,
        min_sample_size=min_sample_size,
    )
    fallback["available"] = False
    fallback["source"] = "python_deterministic_fallback"
    fallback["returncode"] = None
    fallback["cli_path"] = str(cli)
    return fallback


def _wire_payload(
    *,
    holdback: Mapping[str, Any],
    variants: Sequence[Mapping[str, Any]],
    experiment_id: str,
    confidence: float,
    alpha: float,
    beta: float,
    min_detectable_effect: float,
    min_sample_size: float,
) -> str:
    lines = [
        f"experiment_id={experiment_id}",
        f"confidence={float(confidence)}",
        f"alpha={float(alpha)}",
        f"beta={float(beta)}",
        f"min_detectable_effect={float(min_detectable_effect)}",
        f"min_sample_size={float(min_sample_size)}",
        f"holdback.name={holdback.get('name', 'holdback')}",
        f"holdback.impressions={float(holdback.get('impressions', 0.0))}",
        f"holdback.rewards={float(holdback.get('rewards', 0.0))}",
        f"variant_count={len(variants)}",
    ]
    for idx, variant in enumerate(variants):
        lines.extend(
            [
                f"variant.{idx}.name={variant.get('name', '')}",
                f"variant.{idx}.impressions={float(variant.get('impressions', 0.0))}",
                f"variant.{idx}.rewards={float(variant.get('rewards', 0.0))}",
            ]
        )
    return "\n".join(lines) + "\n"


def _python_analyze(
    *,
    holdback: Mapping[str, Any],
    variants: Sequence[Mapping[str, Any]],
    experiment_id: str,
    confidence: float,
    alpha: float,
    beta: float,
    min_detectable_effect: float,
    min_sample_size: float,
) -> dict[str, Any]:
    holdback_arm = _arm(holdback)
    if holdback_arm["impressions"] <= 0.0:
        raise ValueError("holdback.impressions must be positive")
    holdback_arm["rate"] = _rate(holdback_arm["rewards"], holdback_arm["impressions"])
    analyzed = [
        _analyze_variant(
            _arm(variant),
            holdback=holdback_arm,
            confidence=confidence,
            alpha=alpha,
            beta=beta,
            min_detectable_effect=min_detectable_effect,
            min_sample_size=min_sample_size,
        )
        for variant in variants
    ]
    best = max(analyzed, key=lambda v: v["uplift_absolute"])
    return {
        "schema_version": NATIVE_EXPERIMENT_STATS_SCHEMA,
        "engine": {"name": "tryops_experiment_stats", "language": "python", "version": "0.1.0"},
        "experiment_id": experiment_id,
        "confidence": float(confidence),
        "alpha": float(alpha),
        "beta": float(beta),
        "min_detectable_effect": float(min_detectable_effect),
        "min_sample_size": float(min_sample_size),
        "holdback": holdback_arm,
        "variants": analyzed,
        "best_variant": best["name"],
    }


def _arm(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": str(source.get("name", "holdback")),
        "impressions": float(source.get("impressions", 0.0)),
        "rewards": float(source.get("rewards", 0.0)),
        "rate": 0.0,
    }


def _analyze_variant(
    arm: dict[str, Any],
    *,
    holdback: Mapping[str, Any],
    confidence: float,
    alpha: float,
    beta: float,
    min_detectable_effect: float,
    min_sample_size: float,
) -> dict[str, Any]:
    if arm["impressions"] <= 0.0:
        raise ValueError("variant impressions must be positive")
    arm["rate"] = _rate(arm["rewards"], arm["impressions"])
    uplift_absolute = arm["rate"] - holdback["rate"]
    uplift_relative = uplift_absolute / holdback["rate"] if holdback["rate"] > 0 else 0.0
    uplift_ci = _agresti_caffo_ci(
        arm["rewards"],
        arm["impressions"],
        holdback["rewards"],
        holdback["impressions"],
        confidence,
    )
    sequential = _sprt(
        rewards=arm["rewards"],
        impressions=arm["impressions"],
        holdback_rate=holdback["rate"],
        holdback_impressions=holdback["impressions"],
        alpha=alpha,
        beta=beta,
        min_detectable_effect=min_detectable_effect,
        min_sample_size=min_sample_size,
    )
    return {
        **arm,
        "uplift_absolute": uplift_absolute,
        "uplift_relative": uplift_relative,
        "uplift_ci": uplift_ci,
        "sequential": sequential,
    }


def _agresti_caffo_ci(
    rewards: float,
    impressions: float,
    holdback_rewards: float,
    holdback_impressions: float,
    confidence: float,
) -> dict[str, Any]:
    n1 = impressions + 2.0
    n0 = holdback_impressions + 2.0
    p1 = (rewards + 1.0) / n1
    p0 = (holdback_rewards + 1.0) / n0
    diff = p1 - p0
    se = math.sqrt((p1 * (1.0 - p1) / n1) + (p0 * (1.0 - p0) / n0))
    margin = _z_for_confidence(confidence) * se
    lo = diff - margin
    hi = diff + margin
    return {
        "method": "agresti_caffo_adjusted_difference",
        "confidence": float(confidence),
        "lo": lo,
        "hi": hi,
        "excludes_zero": lo > 0.0 or hi < 0.0,
    }


def _sprt(
    *,
    rewards: float,
    impressions: float,
    holdback_rate: float,
    holdback_impressions: float,
    alpha: float,
    beta: float,
    min_detectable_effect: float,
    min_sample_size: float,
) -> dict[str, Any]:
    p0 = _clamp_probability(holdback_rate)
    p1 = _clamp_probability(holdback_rate + min_detectable_effect)
    lower = math.log(beta / (1.0 - alpha))
    upper = math.log((1.0 - beta) / alpha)
    llr = rewards * math.log(p1 / p0) + (impressions - rewards) * math.log((1.0 - p1) / (1.0 - p0))
    if impressions < min_sample_size or holdback_impressions < min_sample_size:
        verdict = "continue"
        early_stop = False
        reason = "minimum_sample_not_met"
    elif llr >= upper:
        verdict = "accept_variant"
        early_stop = True
        reason = "sprt_upper_boundary_crossed"
    elif llr <= lower:
        verdict = "accept_holdback"
        early_stop = True
        reason = "sprt_lower_boundary_crossed"
    else:
        verdict = "continue"
        early_stop = False
        reason = "inside_sprt_boundaries"
    return {
        "method": "wald_sprt_binomial_vs_holdback_rate",
        "p0": p0,
        "p1": p1,
        "log_likelihood_ratio": llr,
        "lower_boundary": lower,
        "upper_boundary": upper,
        "verdict": verdict,
        "early_stop": early_stop,
        "reason": reason,
    }


def _rate(rewards: float, impressions: float) -> float:
    return rewards / impressions if impressions > 0.0 else 0.0


def _z_for_confidence(confidence: float) -> float:
    if abs(confidence - 0.90) < 0.000001:
        return 1.644854
    if abs(confidence - 0.99) < 0.000001:
        return 2.575829
    return 1.959964


def _clamp_probability(value: float) -> float:
    return min(max(float(value), 0.000001), 0.999999)
