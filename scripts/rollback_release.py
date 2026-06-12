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

from tryops.deployment import rollback_release  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a TryOps release rollback.")
    parser.add_argument("package_id")
    parser.add_argument("--packages-dir", type=Path, default=Path("artifacts/deployments"))
    parser.add_argument("--reason", default="manual rollback drill")
    args = parser.parse_args()

    record = rollback_release(
        package_id=args.package_id,
        packages_dir=args.packages_dir,
        reason=args.reason,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
