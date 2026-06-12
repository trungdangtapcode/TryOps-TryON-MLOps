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

from tryops.auth import write_api_key_auth_report  # noqa: E402


DEFAULT_SCENARIOS = [
    {
        "name": "admin_can_evaluate_promotion",
        "key_label": "admin-demo",
        "api_key": "tryops-admin-demo-key",
        "required_scope": "promotion:evaluate",
        "expected_allowed": True,
    },
    {
        "name": "admin_can_create_lineage",
        "key_label": "admin-demo",
        "api_key": "tryops-admin-demo-key",
        "required_scope": "lineage:create",
        "expected_allowed": True,
    },
    {
        "name": "risk_reviewer_can_evaluate_promotion",
        "key_label": "risk-demo",
        "api_key": "tryops-risk-demo-key",
        "required_scope": "promotion:evaluate",
        "expected_allowed": True,
    },
    {
        "name": "risk_reviewer_cannot_create_lineage",
        "key_label": "risk-demo",
        "api_key": "tryops-risk-demo-key",
        "required_scope": "lineage:create",
        "expected_allowed": False,
    },
    {
        "name": "viewer_cannot_evaluate_promotion",
        "key_label": "viewer-demo",
        "api_key": "tryops-viewer-demo-key",
        "required_scope": "promotion:evaluate",
        "expected_allowed": False,
    },
    {
        "name": "missing_key_is_rejected",
        "key_label": "missing",
        "api_key": "",
        "required_scope": "promotion:evaluate",
        "expected_allowed": False,
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate TryOps local API-key authorization scenarios.")
    parser.add_argument("--registry", type=Path, default=Path("configs/api_keys.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/auth/api_key_auth_report.json"))
    args = parser.parse_args()

    report = write_api_key_auth_report(
        scenarios=DEFAULT_SCENARIOS,
        registry_path=args.registry,
        output_path=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
