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

from tryops.supply_chain import write_supply_chain_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TryOps dependency lock, SBOM, and supply-chain evidence.")
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--model-sources", type=Path, default=Path("configs/model_sources.json"))
    parser.add_argument("--dataset-licenses", type=Path, default=Path("configs/dataset_licenses.json"))
    parser.add_argument("--requirements-output", type=Path, default=Path("requirements.lock"))
    parser.add_argument("--dependency-lock-output", type=Path, default=Path("artifacts/eval/supply_chain/dependency_lock.json"))
    parser.add_argument("--sbom-output", type=Path, default=Path("artifacts/eval/supply_chain/sbom.spdx.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eval/supply_chain/supply_chain_report.json"))
    args = parser.parse_args()

    report = write_supply_chain_report(
        pyproject_path=args.pyproject,
        model_sources_path=args.model_sources,
        dataset_licenses_path=args.dataset_licenses,
        requirements_output=args.requirements_output,
        dependency_lock_output=args.dependency_lock_output,
        sbom_output=args.sbom_output,
        output_path=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
