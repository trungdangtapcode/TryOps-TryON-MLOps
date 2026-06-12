from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{config_path} must contain a JSON object")
    return payload


def require_keys(payload: dict[str, Any], required: list[str]) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"missing required config keys: {', '.join(missing)}")

