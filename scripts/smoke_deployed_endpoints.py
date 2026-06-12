#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.endpoint_smoke import run_endpoint_smoke  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test TryOps deployed API endpoints.")
    parser.add_argument("--base-url", default=None, help="Optional deployed API base URL, such as http://127.0.0.1:8000")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/eval/endpoint_smoke"))
    args = parser.parse_args()

    report = run_endpoint_smoke(output_dir=args.output_dir, base_url=args.base_url)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
