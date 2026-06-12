from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_EVALUATION_INDEX_PATH = Path("artifacts/eval/evaluation_index/evaluation_index.json")


def evaluation_index_path() -> Path:
    configured = os.environ.get("TRYOPS_EVALUATION_INDEX_PATH")
    if configured:
        return Path(configured)
    return DEFAULT_EVALUATION_INDEX_PATH


def load_evaluation_index(path: Path | None = None) -> dict[str, Any]:
    index_path = path or evaluation_index_path()
    with index_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != "tryops.evaluation_index.v1":
        raise ValueError(f"unsupported evaluation index schema: {payload.get('schema_version')}")
    return payload
