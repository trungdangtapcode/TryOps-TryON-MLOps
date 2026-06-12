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

from tryops.slo import evaluate_slo_burn_rates, load_slo_config, render_prometheus_burn_rate_rules  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate TryOps workload SLO error-budget burn rates.")
    parser.add_argument("--slos", type=Path, default=Path("configs/service_level_objectives.json"))
    parser.add_argument("--llm-benchmark", type=Path, default=Path("artifacts/eval/llm_baseline/benchmark.json"))
    parser.add_argument("--vton-comparison", type=Path, default=Path("artifacts/eval/vton_comparison/comparison.json"))
    parser.add_argument("--endpoint-smoke", type=Path, default=Path("artifacts/eval/endpoint_smoke/deployed_endpoint_smoke.json"))
    parser.add_argument("--native-cli", type=Path, default=Path("artifacts/native/tryops_burn_rate_cli"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/slo/slo_burn_rate_report.json"))
    parser.add_argument("--rules-output", type=Path, default=Path("infra/prometheus/tryops_burn_rate_alerts.yml"))
    args = parser.parse_args()

    slo_config = load_slo_config(args.slos)
    report = evaluate_slo_burn_rates(
        slo_config=slo_config,
        llm_benchmark=json.loads(args.llm_benchmark.read_text(encoding="utf-8")),
        vton_comparison=json.loads(args.vton_comparison.read_text(encoding="utf-8")),
        endpoint_smoke=json.loads(args.endpoint_smoke.read_text(encoding="utf-8")),
        native_cli_path=args.native_cli,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    args.rules_output.parent.mkdir(parents=True, exist_ok=True)
    args.rules_output.write_text(render_prometheus_burn_rate_rules(slo_config), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
