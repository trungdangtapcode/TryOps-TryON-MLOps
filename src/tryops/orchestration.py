from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ORCHESTRATION_SCHEMA = "tryops.orchestration_dag.v1"
ORCHESTRATION_REPORT_SCHEMA = "tryops.orchestration_report.v1"
DEFAULT_PIPELINE_NAME = "tryops-enterprise-promotion"
DEFAULT_NAMESPACE = "kubeflow-user-example-com"


@dataclass(frozen=True)
class PipelineStep:
    step_id: str
    display_name: str
    component: str
    command: list[str]
    dependencies: list[str] = field(default_factory=list)
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    cache_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.step_id,
            "display_name": self.display_name,
            "component": self.component,
            "command": list(self.command),
            "dependencies": list(self.dependencies),
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "cache_enabled": self.cache_enabled,
        }


def build_tryops_pipeline_spec(
    *,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    namespace: str = DEFAULT_NAMESPACE,
) -> dict[str, Any]:
    steps = [
        PipelineStep(
            step_id="validate-data",
            display_name="Validate dataset manifest",
            component="tryops.pipelines.data_validation.validate_dataset_manifest",
            command=[
                "python",
                "scripts/validate_dataset_manifest.py",
                "samples/data/demo_manifest.json",
                "--output",
                "artifacts/eval/orchestration/data_validation.json",
            ],
            inputs={"dataset_manifest": "samples/data/demo_manifest.json"},
            outputs={"data_validation_report": "artifacts/eval/orchestration/data_validation.json"},
        ),
        PipelineStep(
            step_id="evaluate-vton",
            display_name="Evaluate VTON baseline",
            component="scripts.compare_vton_baselines",
            command=[
                "python",
                "scripts/compare_vton_baselines.py",
                "artifacts/demo/vton/person.png",
                "artifacts/demo/vton/garment.png",
                "--output-dir",
                "artifacts/eval/vton_comparison",
            ],
            dependencies=["validate-data"],
            inputs={"golden_pairs": "samples/eval/golden_vton_pairs.json"},
            outputs={"vton_comparison": "artifacts/eval/vton_comparison/comparison.json"},
        ),
        PipelineStep(
            step_id="benchmark-llm",
            display_name="Benchmark LLM baseline",
            component="scripts.benchmark_llm_baseline",
            command=[
                "python",
                "scripts/benchmark_llm_baseline.py",
                "--prompt-set",
                "samples/eval/golden_prompts.json",
                "--output",
                "artifacts/eval/llm_baseline/benchmark.json",
            ],
            dependencies=["validate-data"],
            inputs={"golden_prompts": "samples/eval/golden_prompts.json"},
            outputs={"llm_benchmark": "artifacts/eval/llm_baseline/benchmark.json"},
        ),
        PipelineStep(
            step_id="generate-supply-chain",
            display_name="Generate dependency lock and SBOM evidence",
            component="scripts.generate_supply_chain_report",
            command=["python", "scripts/generate_supply_chain_report.py", "--output", "artifacts/eval/supply_chain/supply_chain_report.json"],
            outputs={"supply_chain_report": "artifacts/eval/supply_chain/supply_chain_report.json"},
        ),
        PipelineStep(
            step_id="map-governance",
            display_name="Generate governance risk mapping",
            component="scripts.generate_governance_report",
            command=["python", "scripts/generate_governance_report.py", "--output", "artifacts/eval/governance/governance_report.json"],
            outputs={"governance_report": "artifacts/eval/governance/governance_report.json"},
        ),
        PipelineStep(
            step_id="evaluate-promotion",
            display_name="Evaluate promotion policy",
            component="tryops.pipelines.promotion.run_local_promotion_pipeline",
            command=[
                "python",
                "scripts/run_local_promotion_pipeline.py",
                "samples/candidates/vton_candidate_good.json",
                "samples/data/demo_manifest.json",
                "--stage",
                "champion",
                "--output-dir",
                "reports/generated",
            ],
            dependencies=["evaluate-vton", "benchmark-llm", "generate-supply-chain", "map-governance"],
            inputs={
                "candidate": "samples/candidates/vton_candidate_good.json",
                "dataset_manifest": "samples/data/demo_manifest.json",
            },
            outputs={"promotion_decision": "reports/generated/vton-catvton-2026-06-11-001/promotion_decision.json"},
            cache_enabled=False,
        ),
        PipelineStep(
            step_id="package-deployment",
            display_name="Package deployment release",
            component="scripts.package_deployment",
            command=[
                "python",
                "scripts/package_deployment.py",
                "reports/generated/vton-catvton-2026-06-11-001",
                "--profile",
                "production-demo",
                "--output-dir",
                "artifacts/deployments",
                "--previous-candidate-id",
                "vton-catvton-previous",
            ],
            dependencies=["evaluate-promotion"],
            inputs={"promotion_evidence": "reports/generated/vton-catvton-2026-06-11-001"},
            outputs={
                "deployment_manifest": "artifacts/deployments/vton-catvton-2026-06-11-001-production-demo/deployment_manifest.json"
            },
            cache_enabled=False,
        ),
    ]
    return {
        "schema_version": ORCHESTRATION_SCHEMA,
        "pipeline_name": pipeline_name,
        "namespace": namespace,
        "target_orchestrator": "kubeflow-pipelines",
        "created_at": datetime.now(UTC).isoformat(),
        "description": "TryOps enterprise DAG skeleton for data validation, evaluation, governance, promotion, and deployment packaging.",
        "steps": [step.to_dict() for step in steps],
    }


def validate_pipeline_spec(spec: dict[str, Any]) -> dict[str, Any]:
    steps = list(spec.get("steps", []))
    ids = [str(step.get("id", "")) for step in steps]
    duplicate_ids = sorted({step_id for step_id in ids if ids.count(step_id) > 1})
    missing_dependencies = []
    for step in steps:
        step_id = str(step.get("id", ""))
        for dependency in step.get("dependencies", []):
            if dependency not in ids:
                missing_dependencies.append({"step": step_id, "dependency": str(dependency)})

    cycle = _find_cycle(steps)
    topological_order = [] if cycle else _topological_order(steps)
    commandless_steps = sorted(str(step.get("id", "")) for step in steps if not step.get("command"))
    terminal_steps = _terminal_steps(steps)
    passed = bool(steps) and not duplicate_ids and not missing_dependencies and not cycle and not commandless_steps
    return {
        "schema_version": "tryops.orchestration_validation.v1",
        "step_count": len(steps),
        "duplicate_ids": duplicate_ids,
        "missing_dependencies": missing_dependencies,
        "cycle": cycle,
        "topological_order": topological_order,
        "terminal_steps": terminal_steps,
        "commandless_steps": commandless_steps,
        "passed": passed,
    }


def render_kfp_native_manifest(spec: dict[str, Any]) -> str:
    pipeline_name = str(spec["pipeline_name"])
    version_name = f"{pipeline_name}-v1"
    namespace = str(spec["namespace"])
    lines = [
        "apiVersion: pipelines.kubeflow.org/v2beta1",
        "kind: Pipeline",
        "metadata:",
        f"  name: {pipeline_name}",
        f"  namespace: {namespace}",
        "spec:",
        f"  displayName: {pipeline_name}",
        f"  description: {str(spec.get('description', 'TryOps pipeline skeleton'))}",
        "---",
        "apiVersion: pipelines.kubeflow.org/v2beta1",
        "kind: PipelineVersion",
        "metadata:",
        f"  name: {version_name}",
        f"  namespace: {namespace}",
        "spec:",
        f"  displayName: {version_name}",
        f"  pipelineName: {pipeline_name}",
        "  pipelineSpec:",
        "    schemaVersion: tryops.kfp_skeleton.v1",
        "    tasks:",
    ]
    for step in spec["steps"]:
        command = " ".join(step["command"])
        lines.extend(
            [
                f"      - name: {step['id']}",
                f"        displayName: {step['display_name']}",
                f"        componentRef: {step['component']}",
                f"        command: {json.dumps(command)}",
                f"        cacheEnabled: {str(bool(step.get('cache_enabled', True))).lower()}",
                "        dependencies:",
            ]
        )
        dependencies = step.get("dependencies", [])
        if dependencies:
            lines.extend([f"          - {dependency}" for dependency in dependencies])
        else:
            lines.append("          []")
        lines.append("        outputs:")
        outputs = step.get("outputs", {})
        if outputs:
            for name, path in outputs.items():
                lines.append(f"          {name}: {path}")
        else:
            lines.append("          {}")
    lines.append("")
    return "\n".join(lines)


def write_orchestration_skeleton(
    *,
    output_dir: str | Path,
    pipeline_name: str = DEFAULT_PIPELINE_NAME,
    namespace: str = DEFAULT_NAMESPACE,
) -> dict[str, Any]:
    spec = build_tryops_pipeline_spec(pipeline_name=pipeline_name, namespace=namespace)
    validation = validate_pipeline_spec(spec)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    dag_path = output / "tryops_pipeline_dag.json"
    manifest_path = output / "tryops_pipeline.kfp.yaml"
    report_path = output / "orchestration_report.json"
    dag_path.write_text(json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8")
    manifest_path.write_text(render_kfp_native_manifest(spec), encoding="utf-8")
    report = {
        "schema_version": ORCHESTRATION_REPORT_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "pipeline_name": pipeline_name,
        "target_orchestrator": "kubeflow-pipelines",
        "research_sources": {
            "kubeflow_pipelines_overview": "https://www.kubeflow.org/docs/components/pipelines/overview/",
            "kubeflow_compile_pipeline": "https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/compile-a-pipeline/",
            "kubeflow_components": "https://www.kubeflow.org/docs/components/pipelines/user-guides/components/",
        },
        "artifacts": {
            "dag": str(dag_path),
            "kfp_manifest": str(manifest_path),
        },
        "validation": validation,
        "passed": validation["passed"],
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _topological_order(steps: list[dict[str, Any]]) -> list[str]:
    dependencies = {str(step["id"]): set(step.get("dependencies", [])) for step in steps}
    dependents: dict[str, set[str]] = {step_id: set() for step_id in dependencies}
    for step_id, step_dependencies in dependencies.items():
        for dependency in step_dependencies:
            dependents.setdefault(dependency, set()).add(step_id)
    ready = deque(sorted(step_id for step_id, step_dependencies in dependencies.items() if not step_dependencies))
    ordered = []
    while ready:
        step_id = ready.popleft()
        ordered.append(step_id)
        for dependent in sorted(dependents.get(step_id, set())):
            dependencies[dependent].discard(step_id)
            if not dependencies[dependent]:
                ready.append(dependent)
    return ordered


def _find_cycle(steps: list[dict[str, Any]]) -> list[str]:
    ids = {str(step["id"]) for step in steps}
    dependencies = {str(step["id"]): [dep for dep in step.get("dependencies", []) if dep in ids] for step in steps}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str, path: list[str]) -> list[str]:
        if step_id in visiting:
            return path[path.index(step_id) :] + [step_id] if step_id in path else [step_id]
        if step_id in visited:
            return []
        visiting.add(step_id)
        for dependency in dependencies.get(step_id, []):
            cycle = visit(str(dependency), path + [step_id])
            if cycle:
                return cycle
        visiting.remove(step_id)
        visited.add(step_id)
        return []

    for step_id in sorted(dependencies):
        cycle = visit(step_id, [])
        if cycle:
            return cycle
    return []


def _terminal_steps(steps: list[dict[str, Any]]) -> list[str]:
    depended_on = {str(dependency) for step in steps for dependency in step.get("dependencies", [])}
    return sorted(str(step.get("id", "")) for step in steps if str(step.get("id", "")) not in depended_on)
