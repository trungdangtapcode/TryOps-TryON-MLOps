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

from tryops.drift import build_sample_drift_reports  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local TryOps image and prompt drift reports.")
    parser.add_argument("--image-dir", type=Path, default=Path("artifacts/demo/vton"))
    parser.add_argument("--prompt-set", type=Path, default=Path("samples/eval/golden_prompts.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/eval/drift"))
    args = parser.parse_args()

    summary = build_sample_drift_reports(
        image_dir=args.image_dir,
        prompt_set_path=args.prompt_set,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
