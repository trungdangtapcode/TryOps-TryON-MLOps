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

from tryops.dashboards import validate_dashboard_directory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate provisioned TryOps Grafana dashboards.")
    parser.add_argument("--dashboard-dir", type=Path, default=Path("infra/grafana/dashboards"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/dashboards/dashboard_report.json"))
    args = parser.parse_args()

    report = validate_dashboard_directory(args.dashboard_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
