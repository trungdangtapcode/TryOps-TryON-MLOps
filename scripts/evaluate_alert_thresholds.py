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

from tryops.alerts import evaluate_alert_thresholds, load_thresholds, render_prometheus_alert_rules  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate local latency and quality alert thresholds.")
    parser.add_argument("--thresholds", type=Path, default=Path("configs/alert_thresholds.json"))
    parser.add_argument("--llm-benchmark", type=Path, default=Path("artifacts/eval/llm_baseline/benchmark.json"))
    parser.add_argument("--vton-comparison", type=Path, default=Path("artifacts/eval/vton_comparison/comparison.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/alerts/alert_report.json"))
    parser.add_argument("--rules-output", type=Path, default=Path("infra/prometheus/tryops_alerts.yml"))
    args = parser.parse_args()

    thresholds = load_thresholds(args.thresholds)
    llm_benchmark = json.loads(args.llm_benchmark.read_text(encoding="utf-8"))
    vton_comparison = json.loads(args.vton_comparison.read_text(encoding="utf-8"))
    report = evaluate_alert_thresholds(
        thresholds=thresholds,
        llm_benchmark=llm_benchmark,
        vton_comparison=vton_comparison,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    args.rules_output.parent.mkdir(parents=True, exist_ok=True)
    args.rules_output.write_text(render_prometheus_alert_rules(thresholds), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
