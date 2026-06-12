"""Bridge to the native C++ PII/secret redaction engine.

Scrubs secrets and PII out of text at the boundary before logging/persisting.
The match-and-mask hot path lives in ``native/cpp/tryops_redaction``; this module
invokes the compiled binary and falls back to a pure-Python reimplementation so
offline ``make smoke`` still works.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_NATIVE_REDACTION_CLI = Path("artifacts/native/tryops_redaction_cli")

_FNV_OFFSET = 1469598103934665603
_FNV_PRIME = 1099511628211
_MASK = (1 << 64) - 1

# (category, placeholder, pattern, luhn) — order mirrors the C++ engine.
_DETECTORS: list[tuple[str, str, re.Pattern[str], bool]] = [
    ("jwt", "[REDACTED_JWT]", re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), False),
    ("aws_key", "[REDACTED_AWS_KEY]", re.compile(r"AKIA[0-9A-Z]{16}"), False),
    ("github_token", "[REDACTED_GITHUB_TOKEN]", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), False),
    ("api_key", "[REDACTED_API_KEY]", re.compile(r"sk-[A-Za-z0-9]{20,}"), False),
    ("bearer", "[REDACTED_BEARER]", re.compile(r"[Bb]earer\s+[A-Za-z0-9._-]{16,}"), False),
    ("email", "[REDACTED_EMAIL]", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), False),
    ("credit_card", "[REDACTED_CC]", re.compile(r"\b(?:\d[ -]?){13,19}\b"), True),
    ("ssn", "[REDACTED_SSN]", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), False),
    ("ipv4", "[REDACTED_IP]", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), False),
    ("phone", "[REDACTED_PHONE]", re.compile(
        r"(?:\+\d[\d\s().-]{7,}\d)|(?:\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4})|(?:\b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b)"
    ), False),
]


def fnv1a(data: str) -> int:
    h = _FNV_OFFSET
    for b in data.encode("utf-8", "surrogatepass"):
        h ^= b
        h = (h * _FNV_PRIME) & _MASK
    return h


def luhn_valid(digits: str) -> bool:
    if not (13 <= len(digits) <= 19) or not digits.isdigit():
        return False
    total = 0
    dbl = False
    for ch in reversed(digits):
        n = ord(ch) - 48
        if dbl:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        dbl = not dbl
    return total % 10 == 0


def redact_text(text: str) -> dict[str, Any]:
    """Pure-Python reference reimplementation mirroring the C++ engine."""
    counts: dict[str, int] = {}
    total = 0
    current = text
    input_fp = fnv1a(text)
    for category, placeholder, pattern, luhn in _DETECTORS:
        out: list[str] = []
        last = 0
        for m in pattern.finditer(current):
            if luhn:
                only = re.sub(r"\D", "", m.group(0))
                if not luhn_valid(only):
                    continue
            out.append(current[last:m.start()])
            out.append(placeholder)
            last = m.end()
            counts[category] = counts.get(category, 0) + 1
            total += 1
        out.append(current[last:])
        current = "".join(out)
    return {
        "total": total,
        "counts": counts,
        "redacted": current,
        "input_fingerprint": f"{input_fp:x}",
        "output_fingerprint": f"{fnv1a(current):x}",
    }


def evaluate_with_native_redaction(
    text: str,
    *,
    emit_redacted: bool = True,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(
        cli_path
        or os.environ.get("TRYOPS_NATIVE_REDACTION_CLI", DEFAULT_NATIVE_REDACTION_CLI)
    )
    if path.exists():
        args = [str(path)]
        if emit_redacted:
            args.append("--emit-redacted")
        completed = subprocess.run(
            args, input=text, text=True, capture_output=True, check=False
        )
        if completed.stdout.strip():
            report = json.loads(completed.stdout)
            report["engine"] = "native"
            report["cli_path"] = str(path)
            return report

    report = redact_text(text)
    report["engine"] = "python_fallback"
    report["cli_path"] = str(path)
    return report
