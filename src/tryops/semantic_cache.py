from __future__ import annotations

import copy
import json
import math
import os
import re
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


NATIVE_SEMANTIC_CACHE_SCHEMA = "tryops.native_semantic_cache.v1"
SEMANTIC_CACHE_SCHEMA = "tryops.semantic_cache.v1"
DEFAULT_NATIVE_SEMANTIC_CACHE_CLI = Path("artifacts/native/tryops_semantic_cache_cli")


@dataclass(frozen=True)
class SemanticCacheEntry:
    id: str
    prompt: str
    generation: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    energy_wh: float = 0.0


class SemanticCache:
    def __init__(self, *, threshold: float = 0.72, max_entries: int = 256) -> None:
        self.threshold = float(threshold)
        self.max_entries = int(max_entries)
        self._entries: list[SemanticCacheEntry] = []

    def lookup(
        self,
        prompt: str,
        *,
        threshold: float | None = None,
        cli_path: str | Path | None = None,
    ) -> dict[str, Any]:
        return lookup_semantic_cache(
            query=prompt,
            entries=self._entries,
            threshold=self.threshold if threshold is None else threshold,
            cli_path=cli_path,
        )

    def get_generation(self, matched_entry_id: str) -> dict[str, Any] | None:
        for entry in self._entries:
            if entry.id == matched_entry_id:
                return copy.deepcopy(entry.generation)
        return None

    def put(self, *, prompt: str, generation: dict[str, Any], energy_wh: float = 0.0) -> SemanticCacheEntry:
        entry = build_semantic_cache_entry(prompt=prompt, generation=generation, energy_wh=energy_wh)
        self._entries = [existing for existing in self._entries if existing.id != entry.id]
        self._entries.append(entry)
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries :]
        return entry

    def reset(self) -> None:
        self._entries.clear()

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "tryops.semantic_cache_snapshot.v1",
            "threshold": self.threshold,
            "entry_count": len(self._entries),
            "entries": [
                {
                    "id": entry.id,
                    "prompt_fingerprint": prompt_fingerprint(entry.prompt),
                    "input_tokens": entry.input_tokens,
                    "output_tokens": entry.output_tokens,
                    "cost_usd": round(entry.cost_usd, 9),
                    "energy_wh": round(entry.energy_wh, 9),
                }
                for entry in self._entries
            ],
        }


GLOBAL_SEMANTIC_CACHE = SemanticCache()


def lookup_semantic_cache(
    *,
    query: str,
    entries: Iterable[SemanticCacheEntry | dict[str, Any]],
    threshold: float = 0.72,
    cli_path: str | Path | None = None,
) -> dict[str, Any]:
    normalized_entries = [_normalize_entry(entry) for entry in entries]
    cli = Path(str(cli_path or os.environ.get("TRYOPS_NATIVE_SEMANTIC_CACHE_CLI", DEFAULT_NATIVE_SEMANTIC_CACHE_CLI)))
    if cli.exists() and os.access(cli, os.X_OK):
        completed = subprocess.run(
            [str(cli)],
            input=_wire_payload(query=query, entries=normalized_entries, threshold=threshold),
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if completed.returncode == 0:
            result = json.loads(completed.stdout)
            result["available"] = result.get("schema_version") == NATIVE_SEMANTIC_CACHE_SCHEMA
            result["cli_path"] = str(cli)
            result["returncode"] = completed.returncode
            return _attach_public_metadata(result, query=query)
        return {
            "schema_version": NATIVE_SEMANTIC_CACHE_SCHEMA,
            "available": True,
            "cli_path": str(cli),
            "returncode": completed.returncode,
            "lookup": _empty_lookup(threshold=threshold, entry_count=len(normalized_entries)),
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    result = _python_lookup(query=query, entries=normalized_entries, threshold=threshold)
    result["available"] = False
    result["cli_path"] = str(cli)
    result["returncode"] = None
    return _attach_public_metadata(result, query=query)


def build_semantic_cache_entry(
    *,
    prompt: str,
    generation: dict[str, Any],
    energy_wh: float = 0.0,
) -> SemanticCacheEntry:
    prompt_meta = generation.get("prompt", {}) if isinstance(generation.get("prompt"), dict) else {}
    output_meta = generation.get("output", {}) if isinstance(generation.get("output"), dict) else {}
    cost_meta = generation.get("cost_estimate", {}) if isinstance(generation.get("cost_estimate"), dict) else {}
    cacheable_generation = {
        key: copy.deepcopy(value)
        for key, value in generation.items()
        if key
        in {
            "schema_version",
            "status",
            "model",
            "prompt",
            "output",
            "metrics",
            "cost_estimate",
            "safety",
            "structured_answer",
        }
    }
    return SemanticCacheEntry(
        id=f"sc-{prompt_fingerprint(prompt)}",
        prompt=str(prompt),
        generation=cacheable_generation,
        input_tokens=int(prompt_meta.get("estimated_tokens", 0)),
        output_tokens=int(output_meta.get("estimated_tokens", 0)),
        cost_usd=float(cost_meta.get("request_usd", 0.0)),
        energy_wh=float(energy_wh),
    )


def build_cache_metadata(
    *,
    lookup: dict[str, Any],
    matched_generation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    public_lookup = dict(lookup.get("lookup", {}))
    public_lookup["hit"] = bool(public_lookup.get("hit", False)) and matched_generation is not None
    savings = _savings_from_lookup(lookup) if public_lookup["hit"] else _zero_savings()
    return {
        "schema_version": SEMANTIC_CACHE_SCHEMA,
        "lookup": public_lookup,
        "savings": savings,
        "native": {
            "available": bool(lookup.get("available", False)),
            "cli_path": str(lookup.get("cli_path", "")),
            "returncode": lookup.get("returncode"),
        },
        "candidates": lookup.get("candidates", [])[:5],
    }


def reset_semantic_cache() -> None:
    GLOBAL_SEMANTIC_CACHE.reset()


def semantic_cache_snapshot() -> dict[str, Any]:
    return GLOBAL_SEMANTIC_CACHE.snapshot()


def prompt_fingerprint(prompt: str) -> str:
    normalized = " ".join(str(prompt).lower().split())
    return sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _wire_payload(*, query: str, entries: list[SemanticCacheEntry], threshold: float) -> str:
    lines = [
        f"threshold={float(threshold)}",
        f"query={_wire_value(query)}",
        f"entry_count={len(entries)}",
    ]
    for index, entry in enumerate(entries):
        prefix = f"entry.{index}."
        lines.extend(
            [
                f"{prefix}id={_wire_value(entry.id)}",
                f"{prefix}prompt={_wire_value(entry.prompt)}",
                f"{prefix}input_tokens={int(entry.input_tokens)}",
                f"{prefix}output_tokens={int(entry.output_tokens)}",
                f"{prefix}cost_usd={float(entry.cost_usd)}",
                f"{prefix}energy_wh={float(entry.energy_wh)}",
            ]
        )
    return "\n".join(lines) + "\n"


def _wire_value(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _python_lookup(*, query: str, entries: list[SemanticCacheEntry], threshold: float) -> dict[str, Any]:
    query_embedding = _embedding(query)
    candidates = sorted(
        [
            {
                "id": entry.id,
                "score": _cosine(query_embedding, _embedding(entry.prompt)),
                "input_tokens": entry.input_tokens,
                "output_tokens": entry.output_tokens,
                "cost_usd": entry.cost_usd,
                "energy_wh": entry.energy_wh,
            }
            for entry in entries
        ],
        key=lambda item: (-float(item["score"]), str(item["id"])),
    )
    best = candidates[0] if candidates else {}
    hit = bool(candidates) and float(best.get("score", 0.0)) >= threshold
    return {
        "schema_version": NATIVE_SEMANTIC_CACHE_SCHEMA,
        "scanner": {"name": "tryops_semantic_cache", "language": "python", "version": "0.1.0"},
        "lookup": {
            "hit": hit,
            "matched_entry_id": str(best.get("id", "")) if hit else "",
            "score": round(float(best.get("score", 0.0)), 6),
            "threshold": float(threshold),
            "entry_count": len(entries),
            "query_token_count": len(_tokenize(query)),
            "source": "python_deterministic_fallback",
        },
        "candidates": [
            {
                **candidate,
                "score": round(float(candidate["score"]), 6),
                "cost_usd": round(float(candidate["cost_usd"]), 9),
                "energy_wh": round(float(candidate["energy_wh"]), 9),
            }
            for candidate in candidates[:5]
        ],
    }


def _attach_public_metadata(result: dict[str, Any], *, query: str) -> dict[str, Any]:
    lookup = result.setdefault("lookup", _empty_lookup(threshold=0.72, entry_count=0))
    lookup["query_fingerprint"] = prompt_fingerprint(query)
    result["savings"] = _savings_from_lookup(result) if lookup.get("hit") else _zero_savings()
    return result


def _savings_from_lookup(result: dict[str, Any]) -> dict[str, Any]:
    matched_id = str(result.get("lookup", {}).get("matched_entry_id", ""))
    for candidate in result.get("candidates", []):
        if str(candidate.get("id", "")) == matched_id:
            input_tokens = int(float(candidate.get("input_tokens", 0)))
            output_tokens = int(float(candidate.get("output_tokens", 0)))
            return {
                "saved_generation": True,
                "tokens_saved": input_tokens + output_tokens,
                "cost_saved_usd": round(float(candidate.get("cost_usd", 0.0)), 9),
                "energy_saved_wh": round(float(candidate.get("energy_wh", 0.0)), 9),
            }
    return _zero_savings()


def _zero_savings() -> dict[str, Any]:
    return {
        "saved_generation": False,
        "tokens_saved": 0,
        "cost_saved_usd": 0.0,
        "energy_saved_wh": 0.0,
    }


def _empty_lookup(*, threshold: float, entry_count: int) -> dict[str, Any]:
    return {
        "hit": False,
        "matched_entry_id": "",
        "score": 0.0,
        "threshold": float(threshold),
        "entry_count": int(entry_count),
        "query_token_count": 0,
        "source": "unavailable",
    }


def _normalize_entry(entry: SemanticCacheEntry | dict[str, Any]) -> SemanticCacheEntry:
    if isinstance(entry, SemanticCacheEntry):
        return entry
    return SemanticCacheEntry(
        id=str(entry["id"]),
        prompt=str(entry["prompt"]),
        generation=dict(entry.get("generation", {})),
        input_tokens=int(entry.get("input_tokens", 0)),
        output_tokens=int(entry.get("output_tokens", 0)),
        cost_usd=float(entry.get("cost_usd", 0.0)),
        energy_wh=float(entry.get("energy_wh", 0.0)),
    )


def _embedding(text: str) -> dict[str, float]:
    vector: dict[str, float] = {}
    for token in _tokenize(text):
        if len(token) > 1:
            vector[token] = vector.get(token, 0.0) + 1.0
    return vector


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(token, 0.0) for token, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
