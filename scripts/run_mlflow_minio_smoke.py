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

from tryops.pipelines.promotion import run_local_promotion_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Write one promotion run to MLflow backed by MinIO.")
    parser.add_argument("--candidate", type=Path, default=ROOT / "samples/candidates/vton_candidate_good.json")
    parser.add_argument("--dataset", type=Path, default=ROOT / "samples/data/demo_manifest.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/eval/mlflow_minio")
    args = parser.parse_args()

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    result = run_local_promotion_pipeline(
        candidate_payload=candidate,
        dataset_manifest=dataset,
        target_stage="champion",
        output_dir=args.output_dir,
    )
    registry_path = Path(result["run_dir"]) / "mlflow_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    print(json.dumps({"promotion": result, "mlflow_registry": registry}, indent=2, sort_keys=True))
    if registry.get("status") != "ok":
        return 2
    if not registry.get("artifact_uri") or not str(registry.get("artifact_uri")).startswith("mlflow-artifacts:"):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
