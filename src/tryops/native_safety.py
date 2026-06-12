"""Bridge to the native C++ content-safety gate.

The Python reference mirrors the engine's rule set and scoring so verdicts and
per-category hit counts agree with the native binary. Heuristic by design —
cheap, explainable pre-LLM screening, not a replacement for a model classifier.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_NATIVE_SAFETY_CLI = Path("artifacts/native/tryops_safety_cli")

# (pattern, category, weight) — order/weights mirror tryops_safety.cpp.
_RULES: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"ignore (all |the )?(previous|above|prior|earlier) (instructions|prompts?|messages?)", re.I), "injection", 0.6),
    (re.compile(r"disregard (all |the )?(previous|above|prior) (instructions|rules)", re.I), "injection", 0.6),
    (re.compile(r"forget (everything|all|your) (instructions|prior|previous)", re.I), "injection", 0.5),
    (re.compile(r"you are (now|no longer)\b", re.I), "injection", 0.4),
    (re.compile(r"\b(jailbreak|do anything now|DAN)\b", re.I), "injection", 0.6),
    (re.compile(r"pretend (you are|to be) (an? )?(unfiltered|uncensored|evil)", re.I), "injection", 0.5),
    (re.compile(r"developer mode|sudo mode|admin override", re.I), "injection", 0.4),
    (re.compile(r"(reveal|show|print|repeat|leak|output) (me )?(your |the )?(initial |original |hidden )?(system )?(prompt|instructions|rules)", re.I), "exfiltration", 0.6),
    (re.compile(r"repeat (the words|everything) (above|before)", re.I), "exfiltration", 0.5),
    (re.compile(r"what (are|were) your (initial |original )?(instructions|system prompt)", re.I), "exfiltration", 0.5),
    (re.compile(r"\b(kill|murder|harm|hurt) (yourself|themselves|them|him|her|people)\b", re.I), "toxicity", 0.7),
    (re.compile(r"\b(idiot|moron|stupid|worthless|pathetic)\b", re.I), "toxicity", 0.3),
    (re.compile(r"\b(hate|despise) (you|them|all)\b", re.I), "toxicity", 0.3),
]


@dataclass
class SafetyThresholds:
    flag: float = 0.4
    block: float = 0.8


def classify(text: str, thresholds: SafetyThresholds | None = None) -> dict[str, Any]:
    th = thresholds or SafetyThresholds()
    lowered = text.lower()
    categories: dict[str, int] = {}
    injection = exfiltration = toxicity = 0
    score = 0.0
    for pattern, category, weight in _RULES:
        hits = len(pattern.findall(lowered))
        if hits:
            categories[category] = categories.get(category, 0) + hits
            if category == "injection":
                injection += hits
            elif category == "exfiltration":
                exfiltration += hits
            else:
                toxicity += hits
            score += weight + (hits - 1) * (weight * 0.5)
    risk = min(1.0, score)
    verdict = "block" if risk >= th.block else "flag" if risk >= th.flag else "allow"
    return {
        "verdict": verdict,
        "risk_score": round(risk, 4),
        "injection_hits": injection,
        "exfiltration_hits": exfiltration,
        "toxicity_hits": toxicity,
        "categories": categories,
    }


def evaluate_with_native_safety(
    text: str,
    *,
    thresholds: SafetyThresholds | None = None,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    th = thresholds or SafetyThresholds()
    path = Path(cli_path or os.environ.get("TRYOPS_NATIVE_SAFETY_CLI", DEFAULT_NATIVE_SAFETY_CLI))
    if path.exists():
        completed = subprocess.run(
            [str(path), "--flag", str(th.flag), "--block", str(th.block)],
            input=text, text=True, capture_output=True, check=False,
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            report["exit_code"] = completed.returncode
            return report

    report = classify(text, th)
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report
