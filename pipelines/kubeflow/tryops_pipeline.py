from __future__ import annotations

"""Optional Kubeflow SDK bridge for the TryOps orchestration skeleton."""

from pathlib import Path

from tryops.orchestration import DEFAULT_NAMESPACE, DEFAULT_PIPELINE_NAME, write_orchestration_skeleton


def compile_local_skeleton(
    *,
    output_dir: str | Path = "artifacts/eval/orchestration",
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    namespace: str = DEFAULT_NAMESPACE,
) -> dict[str, object]:
    return write_orchestration_skeleton(
        output_dir=output_dir,
        pipeline_name=pipeline_name,
        namespace=namespace,
    )
