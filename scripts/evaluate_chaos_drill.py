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

from tryops.chaos import run_chaos_drill  # noqa: E402
from tryops.slo import load_slo_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic TryOps chaos drill and auto-rollback evidence.")
    parser.add_argument("--slos", type=Path, default=Path("configs/service_level_objectives.json"))
    parser.add_argument("--package-id", default="vton-catvton-2026-06-11-001-production-demo")
    parser.add_argument("--packages-dir", type=Path, default=Path("artifacts/deployments"))
    parser.add_argument("--native-chaos-cli", type=Path, default=Path("artifacts/native/tryops_chaos_cli"))
    parser.add_argument("--native-burn-cli", type=Path, default=Path("artifacts/native/tryops_burn_rate_cli"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/chaos/chaos_drill_report.json"))
    args = parser.parse_args()

    report = run_chaos_drill(
        slo_config=load_slo_config(args.slos),
        package_id=args.package_id,
        packages_dir=args.packages_dir,
        native_chaos_cli=args.native_chaos_cli,
        native_burn_cli=args.native_burn_cli,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
