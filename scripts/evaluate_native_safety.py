#!/usr/bin/env python3
"""Screen a batch of prompts with the native content-safety gate and write an
auditable report (per-prompt verdict + aggregate), cross-checking each verdict
against the Python reference.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_safety import (  # noqa: E402
    SafetyThresholds,
    classify,
    evaluate_with_native_safety,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Native content-safety batch screen.")
    parser.add_argument("--input", type=Path, default=Path("samples/safety/prompts.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/safety/safety_report.json"))
    parser.add_argument("--flag", type=float, default=0.4)
    parser.add_argument("--block", type=float, default=0.8)
    parser.add_argument("--min-label-accuracy", type=float, default=1.0)
    parser.add_argument("--cli", type=Path, default=None)
    args = parser.parse_args()

    th = SafetyThresholds(flag=args.flag, block=args.block)
    prompts = [
        json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line
    ]

    results = []
    counts = {"allow": 0, "flag": 0, "block": 0}
    correct_label = 0
    disagreements = 0
    for p in prompts:
        text = p["text"]
        report = evaluate_with_native_safety(text, thresholds=th, cli_path=args.cli)
        reference = classify(text, th)
        if report["verdict"] != reference["verdict"]:
            disagreements += 1
        counts[report["verdict"]] += 1
        # optional ground-truth label for a crude accuracy signal
        expect = p.get("expect")  # "safe" or "unsafe"
        if expect is not None:
            predicted_unsafe = report["verdict"] in ("flag", "block")
            if (expect == "unsafe") == predicted_unsafe:
                correct_label += 1
        results.append({"text": text[:120], "verdict": report["verdict"],
                        "risk_score": report["risk_score"], "expect": expect})

    labeled = [p for p in prompts if p.get("expect") is not None]
    out = {
        "schema_version": "tryops.native_safety.report.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "input": str(args.input),
        "engine": results[0]["verdict"] and evaluate_with_native_safety(
            prompts[0]["text"], thresholds=th, cli_path=args.cli
        ).get("engine") if prompts else "none",
        "thresholds": {"flag": args.flag, "block": args.block},
        "min_label_accuracy": args.min_label_accuracy,
        "total": len(prompts),
        "verdict_counts": counts,
        "reference_disagreements": disagreements,
        "label_accuracy": (correct_label / len(labeled)) if labeled else None,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    acc = out["label_accuracy"]
    print(
        f"[safety] engine={out['engine']} total={out['total']} "
        f"allow={counts['allow']} flag={counts['flag']} block={counts['block']} "
        f"label_accuracy={acc if acc is None else round(acc, 3)} "
        f"reference_disagreements={disagreements}"
    )
    print(f"[safety] wrote {args.output}")
    accuracy_ok = out["label_accuracy"] is None or out["label_accuracy"] >= args.min_label_accuracy
    return 0 if disagreements == 0 and accuracy_ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
