"""LLM-as-judge for Theme N — Claude judge with a deterministic offline fallback.

When ``ANTHROPIC_API_KEY`` is set and the SDK is importable, answer quality is
scored by a Claude model (``claude-haiku-4-5`` for cheap bulk scoring,
``claude-opus-4-8`` for tie-breaks) using structured outputs so every verdict is
validated JSON. The judge prompt is hashed and the model id pinned, so each
verdict is auditable and reproducible. Without a key it degrades to the
model-agnostic concept-coverage rubric, keeping the pipeline and ``make smoke``
offline. The judge is an *orthogonal* quality signal to the rubric — their
agreement (Cohen's kappa) calibrates how much to trust it.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Sequence

from tryops.evaluation import concept_coverage_score

JUDGE_MODEL_BULK = "claude-haiku-4-5"
JUDGE_MODEL_TIEBREAK = "claude-opus-4-8"

_JUDGE_SYSTEM = (
    "You are a strict, fair evaluation judge for an MLOps benchmark. Score how well "
    "an assistant ANSWER satisfies the listed expected characteristics for the given "
    "PROMPT. Reward correct, relevant, well-grounded answers regardless of exact "
    "wording. Return only the structured verdict."
)

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number"},
        "met_criteria": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
    },
    "required": ["score", "met_criteria", "reasoning"],
    "additionalProperties": False,
}


def judge_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return True


def _build_user_prompt(prompt: str, answer: str, expected: Sequence[str]) -> str:
    criteria = "\n".join(f"- {c}" for c in expected) or "- (answer is relevant and correct)"
    return (
        f"PROMPT:\n{prompt}\n\nANSWER:\n{answer}\n\nEXPECTED CHARACTERISTICS:\n{criteria}\n\n"
        "Score from 0.0 (fails all) to 1.0 (fully satisfies). List which characteristics are met."
    )


def prompt_fingerprint(prompt: str, answer: str, expected: Sequence[str]) -> str:
    payload = _JUDGE_SYSTEM + "\x00" + _build_user_prompt(prompt, answer, expected)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def score_answer(
    prompt: str,
    answer: str,
    expected_characteristics: Sequence[str],
    *,
    model: str = JUDGE_MODEL_BULK,
) -> dict[str, Any]:
    """Score one answer in [0,1]. Uses a Claude judge when available, else the
    deterministic offline rubric. Always returns the same shape."""

    fingerprint = prompt_fingerprint(prompt, answer, list(expected_characteristics))
    if not judge_available():
        rubric = concept_coverage_score(answer, list(expected_characteristics))
        return {
            "score": rubric["score"],
            "met_criteria": [
                p["characteristic"] for p in rubric["per_characteristic"] if p["coverage"] >= 0.6
            ],
            "reasoning": "offline concept-coverage rubric (no ANTHROPIC_API_KEY)",
            "source": "offline-rubric",
            "model": None,
            "prompt_sha": fingerprint,
        }
    try:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": _build_user_prompt(prompt, answer, list(expected_characteristics))}],
            output_config={"format": {"type": "json_schema", "schema": _VERDICT_SCHEMA}},
        )
        text = next(b.text for b in response.content if b.type == "text")
        verdict = json.loads(text)
        return {
            "score": round(float(verdict["score"]), 6),
            "met_criteria": list(verdict.get("met_criteria", [])),
            "reasoning": str(verdict.get("reasoning", "")),
            "source": "claude-judge",
            "model": model,
            "prompt_sha": fingerprint,
        }
    except Exception as exc:  # never break the pipeline on a judge failure
        rubric = concept_coverage_score(answer, list(expected_characteristics))
        return {
            "score": rubric["score"],
            "met_criteria": [],
            "reasoning": f"judge failed ({type(exc).__name__}), fell back to rubric",
            "source": "offline-rubric-fallback",
            "model": None,
            "prompt_sha": fingerprint,
        }
