"""Rigorous evaluation primitives for Theme N.

Statistically honest comparison of model variants: bootstrap confidence
intervals, a paired bootstrap significance test on quality deltas, Cohen's kappa
for judge-vs-rubric agreement, and a model-agnostic concept-coverage scorer that
gives real models partial credit (fixing the rubric-overfit failure documented in
the final report — exact-phrase rubrics scored fluent real answers at ~0.25).

Pure standard library, deterministic (seeded), and unit-tested without a GPU.
"""

from __future__ import annotations

import random
import re
from statistics import mean
from typing import Callable, Sequence

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "of", "to", "in", "on",
    "for", "with", "as", "is", "are", "be", "by", "that", "this", "it", "its",
    "can", "should", "must", "may", "will", "at", "from", "into", "than", "not",
}


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.split(r"[^a-z0-9]+", str(text).lower()) if t and t not in _STOPWORDS
    }


def concept_coverage_score(output_text: str, expected_characteristics: Sequence[str]) -> dict:
    """Model-agnostic quality: average fraction of each expected concept's content
    words present in the output. Continuous (partial credit), so paraphrases score
    fairly rather than failing exact-phrase matching."""

    out = _tokens(output_text)
    if not expected_characteristics:
        return {"score": 1.0, "per_characteristic": []}
    per: list[dict] = []
    for characteristic in expected_characteristics:
        concept = _tokens(characteristic.removeprefix("mentions ").removeprefix("Mentions "))
        coverage = (len(concept & out) / len(concept)) if concept else 1.0
        per.append({"characteristic": characteristic, "coverage": round(coverage, 6)})
    score = mean(p["coverage"] for p in per)
    return {"score": round(score, 6), "per_characteristic": per}


def bootstrap_ci(
    values: Sequence[float],
    *,
    statistic: Callable[[Sequence[float]], float] = mean,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict:
    """Percentile bootstrap confidence interval for ``statistic`` over ``values``."""

    vals = [float(v) for v in values]
    if not vals:
        raise ValueError("values cannot be empty")
    point = float(statistic(vals))
    if len(vals) == 1:
        return {"point": round(point, 6), "ci_lo": round(point, 6), "ci_hi": round(point, 6),
                "confidence": confidence, "n": 1}
    rng = random.Random(seed)
    n = len(vals)
    resampled = []
    for _ in range(n_resamples):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        resampled.append(float(statistic(sample)))
    resampled.sort()
    lo_idx = int((1.0 - confidence) / 2.0 * n_resamples)
    hi_idx = min(n_resamples - 1, int((1.0 + confidence) / 2.0 * n_resamples))
    return {
        "point": round(point, 6),
        "ci_lo": round(resampled[lo_idx], 6),
        "ci_hi": round(resampled[hi_idx], 6),
        "confidence": confidence,
        "n": n,
    }


def paired_significance(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_resamples: int = 2000,
    seed: int = 0,
) -> dict:
    """Paired bootstrap test on the per-item difference ``a - b``.

    Returns the mean difference, its bootstrap CI, and a two-sided bootstrap
    p-value (fraction of resampled mean-diffs on the opposite side of zero,
    doubled). Significant at 0.05 when the CI excludes zero.
    """

    if len(a) != len(b):
        raise ValueError("paired inputs must be the same length")
    diffs = [float(x) - float(y) for x, y in zip(a, b)]
    if not diffs:
        raise ValueError("inputs cannot be empty")
    observed = mean(diffs)
    if len(diffs) == 1:
        return {"mean_diff": round(observed, 6), "ci_lo": round(observed, 6),
                "ci_hi": round(observed, 6), "p_value": 1.0, "significant": False, "n": 1}
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_resamples):
        means.append(mean(diffs[rng.randrange(n)] for _ in range(n)))
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[min(n_resamples - 1, int(0.975 * n_resamples))]
    # two-sided p: how often resamples land on the opposite side of zero from observed
    if observed >= 0:
        tail = sum(1 for m in means if m <= 0) / n_resamples
    else:
        tail = sum(1 for m in means if m >= 0) / n_resamples
    p_value = min(1.0, 2.0 * tail)
    return {
        "mean_diff": round(observed, 6),
        "ci_lo": round(lo, 6),
        "ci_hi": round(hi, 6),
        "p_value": round(p_value, 6),
        "significant": not (lo <= 0.0 <= hi),
        "n": n,
    }


def cohens_kappa(rater_a: Sequence, rater_b: Sequence) -> float:
    """Cohen's kappa for two raters over paired categorical labels (e.g. judge vs
    rubric pass/fail, or pairwise winner). 1.0 = perfect, 0 = chance."""

    if len(rater_a) != len(rater_b):
        raise ValueError("raters must be the same length")
    n = len(rater_a)
    if n == 0:
        raise ValueError("raters cannot be empty")
    po = sum(1 for x, y in zip(rater_a, rater_b) if x == y) / n
    labels = set(rater_a) | set(rater_b)
    pe = 0.0
    for label in labels:
        pa = sum(1 for x in rater_a if x == label) / n
        pb = sum(1 for y in rater_b if y == label) / n
        pe += pa * pb
    if pe >= 1.0:
        return 1.0
    return round((po - pe) / (1.0 - pe), 6)
