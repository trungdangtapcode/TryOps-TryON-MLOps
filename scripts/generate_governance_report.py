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

from tryops.governance import write_governance_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TryOps NIST/OWASP governance risk mapping evidence.")
    parser.add_argument("--controls", type=Path, default=Path("configs/governance_risk_controls.json"))
    parser.add_argument("--llm-security-cases", type=Path, default=Path("samples/security/llm_security_cases.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/governance/governance_report.json"))
    args = parser.parse_args()

    report = write_governance_report(
        controls_path=args.controls,
        output_path=args.output,
        llm_security_cases_path=args.llm_security_cases,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
